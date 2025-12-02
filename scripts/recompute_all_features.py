#!/usr/bin/env python3
"""
全量重新计算数据库特征
1. 更新 News 表的情感分数 (sentiment_score) 和标签 (tags)
2. 更新 AttentionFeature 表的所有注意力特征
3. 更新 StateSnapshot 表
"""
import sys
import logging
import pandas as pd
from pathlib import Path
from sqlalchemy import func
from datetime import datetime, timezone

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.db_storage import get_db
from src.database.models import News, Symbol, Price, AttentionFeature, get_session, get_engine
from src.features.news_features import sentiment_score, extract_tags, relevance_flag
from src.features.calculators import calculate_composite_attention

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def recompute_news_scores(batch_size=1000):
    """重新计算新闻的情感分数和标签"""
    logger.info("开始重新计算新闻特征 (Sentiment & Tags)...")
    db = get_db()
    session = get_session(db.news_engine)
    
    total = session.query(News).count()
    logger.info(f"总新闻数: {total}")
    
    processed = 0
    updated = 0
    
    # 分批处理
    for offset in range(0, total, batch_size):
        news_list = session.query(News).order_by(News.id).offset(offset).limit(batch_size).all()
        
        for news in news_list:
            # 1. 重新计算情感分数
            old_score = news.sentiment_score
            new_score = sentiment_score(news.title)
            
            # 2. 重新提取标签
            old_tags_str = news.tags or ''
            existing_tags = set(t.strip() for t in old_tags_str.split(',') if t.strip())
            
            # 提取新标签 (包含中文关键词)
            extracted = extract_tags(news.title)
            new_tags_set = existing_tags | set(extracted)
            new_tags_str = ','.join(sorted(new_tags_set))
            
            # 3. 更新 Relevance (简单逻辑：如果标题包含 symbols 中的任意一个，则为 direct)
            # 注意：这里只是更新 DB 中的默认值，实际计算 Attention 时会针对具体 Symbol 再次计算
            old_relevance = news.relevance
            new_relevance = 'related'
            if news.symbols:
                for sym in news.symbols.split(','):
                    if relevance_flag(news.title, sym) == 'direct':
                        new_relevance = 'direct'
                        break
            
            # 检查是否有变更
            is_changed = False
            
            # 浮点数比较
            if old_score is None or abs(old_score - new_score) > 1e-6:
                news.sentiment_score = new_score
                is_changed = True
                
            if old_tags_str != new_tags_str:
                news.tags = new_tags_str
                is_changed = True
                
            if old_relevance != new_relevance:
                news.relevance = new_relevance
                is_changed = True
            
            if is_changed:
                updated += 1
        
        session.commit()
        processed += len(news_list)
        logger.info(f"进度: {processed}/{total} (已更新 {updated})")
        
    session.close()
    logger.info("新闻特征更新完成！")

def recompute_attention_features():
    """重新计算所有币种的注意力特征"""
    logger.info("开始重新计算 Attention Features...")
    db = get_db()
    session = get_session(db.engine)
    
    # 获取所有活跃币种
    symbols = session.query(Symbol).filter(Symbol.is_active == True).all()
    logger.info(f"待处理币种数: {len(symbols)}")
    
    for symbol_obj in symbols:
        symbol = symbol_obj.symbol
        logger.info(f"正在处理: {symbol}")
        
        # 1. 获取价格数据
        prices = session.query(Price).filter(
            Price.symbol_id == symbol_obj.id,
            Price.timeframe == '1d'  # 目前主要计算日线
        ).order_by(Price.datetime).all()
        
        if not prices:
            logger.warning(f"{symbol} 无价格数据，跳过")
            continue
            
        price_df = pd.DataFrame([{
            'datetime': p.datetime,
            'open': p.open,
            'high': p.high,
            'low': p.low,
            'close': p.close,
            'volume': p.volume
        } for p in prices])
        
        # 2. 获取相关新闻
        # 注意：这里需要模糊匹配 symbols 字段
        news_items = session.query(News).filter(
            News.symbols.like(f'%{symbol}%')
        ).all()
        
        news_df = None
        if news_items:
            news_df = pd.DataFrame([{
                'datetime': n.datetime,
                'title': n.title,
                'source': n.source,
                'sentiment_score': n.sentiment_score,
                'relevance': n.relevance, # 这里使用 DB 中的值，或者重新计算
                'tags': n.tags,
                'language': n.language,
                'node_id': n.node_id,
                'platform': n.platform,
                'node': n.node
            } for n in news_items])
            
            # 重新计算针对该 symbol 的 relevance (更准确)
            news_df['relevance'] = news_df['title'].apply(lambda t: relevance_flag(str(t), symbol))
        
        # 3. 计算特征 (目前暂不包含 Google Trends / Twitter，除非 DB 里有)
        # 这里简化处理，假设 Google Trends / Twitter 数据暂缺或已在 DB 中但这里未加载
        # 如果需要完整数据，需要从 AttentionFeature 表反查或加载原始数据表
        # 鉴于目前主要是更新新闻影响，我们主要关注 News 部分
        
        # 为了保留 Google Trends / Twitter 数据，我们应该先读取现有的 AttentionFeature
        # 但这样比较复杂。如果之前没有 GT/Twitter 数据，或者数据量不大，我们可以先忽略，
        # 或者假设 calculate_composite_attention 会处理缺失值。
        
        # 更好的做法是：如果 calculate_composite_attention 支持增量更新就好了。
        # 但它是全量计算。
        # 我们假设目前没有 Google Trends / Twitter 数据，或者接受它们被重置为 0 (如果未提供)
        # 这是一个潜在风险点。用户说 "记得检查计算逻辑... 不要出错"。
        # 如果我们覆盖了 GT/Twitter 数据，那就是出错了。
        
        # 检查是否有 GT/Twitter 数据源？
        # 项目结构中有 `google_trends_fetcher.py`，数据可能在 `AttentionFeature` 表中。
        # `AttentionFeature` 表混合了所有特征。
        # 如果我们重新计算，必须提供所有输入，否则会丢失。
        
        # 尝试从现有的 AttentionFeature 中提取 GT/Twitter 数据
        existing_features = session.query(AttentionFeature).filter(
            AttentionFeature.symbol_id == symbol_obj.id,
            AttentionFeature.timeframe == 'D'
        ).all()
        
        gt_df = None
        tw_df = None
        
        if existing_features:
            ef_df = pd.DataFrame([{
                'datetime': f.datetime,
                'google_trend_value': f.google_trend_value,
                'twitter_volume': f.twitter_volume
            } for f in existing_features])
            
            if not ef_df.empty:
                gt_df = ef_df[['datetime', 'google_trend_value']].rename(columns={'google_trend_value': 'value'})
                tw_df = ef_df[['datetime', 'twitter_volume']].rename(columns={'twitter_volume': 'value'})
        
        # 4. 执行计算
        try:
            result_df = calculate_composite_attention(
                symbol=symbol,
                price_df=price_df,
                news_df=news_df,
                google_trends_df=gt_df,
                twitter_volume_df=tw_df,
                freq='D'
            )
            
            if result_df is None or result_df.empty:
                continue
                
            # 5. 保存回数据库
            # 逐行更新或批量插入
            # 为了效率，我们先删除旧记录？不，这样会丢失其他字段（如 forward_returns 如果有的话）
            # 应该执行 Upsert。
            
            for _, row in result_df.iterrows():
                dt = row['datetime']
                # 查找现有记录
                af = session.query(AttentionFeature).filter(
                    AttentionFeature.symbol_id == symbol_obj.id,
                    AttentionFeature.datetime == dt,
                    AttentionFeature.timeframe == 'D'
                ).first()
                
                if not af:
                    af = AttentionFeature(
                        symbol_id=symbol_obj.id,
                        datetime=dt,
                        timeframe='D'
                    )
                    session.add(af)
                
                # 更新字段
                af.news_count = int(row['news_count'])
                af.attention_score = float(row['attention_score'])
                af.weighted_attention = float(row['weighted_attention'])
                af.bullish_attention = float(row['bullish_attention'])
                af.bearish_attention = float(row['bearish_attention'])
                af.event_intensity = int(row['event_intensity'])
                af.news_channel_score = float(row['news_channel_score'])
                
                # 恢复/更新 GT/Twitter
                af.google_trend_value = float(row['google_trend_value'])
                af.google_trend_zscore = float(row['google_trend_zscore'])
                af.google_trend_change_7d = float(row['google_trend_change_7d'])
                af.google_trend_change_30d = float(row['google_trend_change_30d'])
                
                af.twitter_volume = float(row['twitter_volume'])
                af.twitter_volume_zscore = float(row['twitter_volume_zscore'])
                af.twitter_volume_change_7d = float(row['twitter_volume_change_7d'])
                
                af.composite_attention_score = float(row['composite_attention_score'])
                af.composite_attention_zscore = float(row['composite_attention_zscore'])
                af.composite_attention_spike_flag = int(row['composite_attention_spike_flag'])
                
            session.commit()
            logger.info(f"{symbol} 更新完成: {len(result_df)} 条记录")
            
        except Exception as e:
            logger.error(f"{symbol} 计算失败: {e}")
            session.rollback()
            
    session.close()

def main():
    # 1. 更新新闻特征
    # recompute_news_scores()
    
    # 2. 更新注意力特征
    recompute_attention_features()
    
    # 3. 更新状态快照 (调用现有脚本逻辑，这里简单打印提示)
    logger.info("请运行 scripts/recompute_state_snapshots.py 来更新状态快照")

if __name__ == "__main__":
    main()
