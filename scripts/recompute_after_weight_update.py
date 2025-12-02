#!/usr/bin/env python3
"""
重新计算因新闻源权重更新而受影响的注意力特征

权重更新后，以下字段需要重新计算：
- weighted_attention
- bullish_attention  
- bearish_attention
- news_channel_score
- composite_attention_score
- composite_attention_zscore
- composite_attention_spike_flag
- detected_events

不需要更新的字段（外部数据源）：
- google_trend_* (Google Trends 数据)
- twitter_volume_* (Twitter 数据)
- news_count (纯计数)
- attention_score (仅基于 news_count)
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from src.config.settings import DATABASE_URL
from src.database.models import Symbol, AttentionFeature, News
from src.features.calculators import calculate_composite_attention
from src.features.event_detectors import detect_events_per_row
from src.data.db_storage import get_db
import pandas as pd


def get_symbols_to_update(session, symbols_filter=None):
    """获取需要更新的 symbols"""
    query = session.query(Symbol).filter(Symbol.is_active == True)
    if symbols_filter:
        query = query.filter(Symbol.symbol.in_(symbols_filter))
    return [s.symbol for s in query.all()]


def recompute_features_for_symbol(symbol: str, timeframe: str = '1d', dry_run: bool = False):
    """重新计算单个 symbol 的注意力特征"""
    
    print(f"\n{'[DRY RUN] ' if dry_run else ''}处理 {symbol} ({timeframe})...")
    
    db = get_db()
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # 标准化 timeframe 格式
    # 数据库存储: 'D', '4H'
    # API 查询: '1d', '4h'
    freq_map = {'1d': 'D', '4h': '4H', 'D': 'D', '4H': '4H'}
    freq_for_calc = freq_map.get(timeframe, 'D')  # 用于 calculate_composite_attention
    freq_for_db = freq_for_calc  # 数据库也使用 'D', '4H'
    
    # 价格数据查询需要小写格式
    timeframe_for_price = timeframe.lower()  # '1d' or '4h'
    
    try:
        # 1. 获取该 symbol 的价格数据
        symbol_obj = session.query(Symbol).filter(Symbol.symbol == symbol).first()
        if not symbol_obj:
            print(f"  ❌ 未找到 symbol: {symbol}")
            return False
        
        price_data = db.get_prices(symbol, timeframe=timeframe_for_price)
        if price_data is None or price_data.empty:
            print(f"  ⚠️  无价格数据")
            return False
        
        # 2. 获取新闻数据
        news_data = db.get_news(symbols=[symbol])
        if news_data is None or news_data.empty:
            print(f"  ⚠️  无新闻数据，跳过")
            return False
        
        # 3. 获取 Google Trends 和 Twitter 数据（这些不需要重算，但计算时需要）
        google_trends = None
        twitter_volume = None
        
        # 尝试从现有 attention_features 中提取 Google/Twitter 数据
        existing_features = session.query(AttentionFeature).filter(
            AttentionFeature.symbol_id == symbol_obj.id,
            AttentionFeature.timeframe == freq_for_db
        ).all()
        
        if existing_features:
            google_trends = pd.DataFrame([{
                'datetime': f.datetime,
                'google_trend_value': f.google_trend_value or 0.0
            } for f in existing_features])
            
            twitter_volume = pd.DataFrame([{
                'datetime': f.datetime,
                'twitter_volume': f.twitter_volume or 0.0
            } for f in existing_features])
        
        print(f"  📊 新闻数据: {len(news_data)} 条")
        print(f"  💰 价格数据: {len(price_data)} 行")
        print(f"  🔍 Google Trends: {len(google_trends) if google_trends is not None else 0} 行")
        print(f"  🐦 Twitter: {len(twitter_volume) if twitter_volume is not None else 0} 行")
        
        # 4. 重新计算注意力特征
        result_df = calculate_composite_attention(
            symbol=symbol,
            price_df=price_data,
            news_df=news_data,
            google_trends_df=google_trends,
            twitter_volume_df=twitter_volume,
            freq=freq_for_calc
        )
        
        if result_df is None or result_df.empty:
            print(f"  ❌ 计算失败")
            return False
        
        # 5. 检测事件
        result_df = detect_events_per_row(result_df)
        
        # 6. 更新数据库
        if not dry_run:
            updated_count = 0
            for _, row in result_df.iterrows():
                record = {
                    'datetime': row['datetime'],
                    'timeframe': row['timeframe'],
                    'weighted_attention': row.get('weighted_attention', 0.0),
                    'bullish_attention': row.get('bullish_attention', 0.0),
                    'bearish_attention': row.get('bearish_attention', 0.0),
                    'news_channel_score': row.get('news_channel_score', 0.0),
                    'composite_attention_score': row.get('composite_attention_score', 0.0),
                    'composite_attention_zscore': row.get('composite_attention_zscore', 0.0),
                    'composite_attention_spike_flag': row.get('composite_attention_spike_flag', 0),
                    'detected_events': row.get('detected_events'),
                }
                
                # 查找并更新现有记录
                existing = session.query(AttentionFeature).filter(
                    AttentionFeature.symbol_id == symbol_obj.id,
                    AttentionFeature.datetime == record['datetime'],
                    AttentionFeature.timeframe == freq_for_db
                ).first()
                
                if existing:
                    # 只更新受影响的字段，保留 Google/Twitter 数据
                    existing.weighted_attention = record['weighted_attention']
                    existing.bullish_attention = record['bullish_attention']
                    existing.bearish_attention = record['bearish_attention']
                    existing.news_channel_score = record['news_channel_score']
                    existing.composite_attention_score = record['composite_attention_score']
                    existing.composite_attention_zscore = record['composite_attention_zscore']
                    existing.composite_attention_spike_flag = record['composite_attention_spike_flag']
                    existing.detected_events = record['detected_events']
                    updated_count += 1
            
            session.commit()
            print(f"  ✅ 已更新 {updated_count} 条记录")
        else:
            print(f"  🔍 [DRY RUN] 将更新 {len(result_df)} 条记录")
            # 显示前后对比示例（显示最近有数据的记录）
            if existing_features and len(existing_features) > 0:
                print("\n  📊 样本对比（最近有权重数据的5条）：")
                shown_count = 0
                for _, new_row in result_df.sort_values('datetime', ascending=False).iterrows():
                    old_feature = next((f for f in existing_features if f.datetime == new_row['datetime']), None)
                    if old_feature and old_feature.weighted_attention > 0:
                        shown_count += 1
                        print(f"\n    [{shown_count}] {new_row['datetime'].strftime('%Y-%m-%d')}:")
                        print(f"      weighted_attention:  {old_feature.weighted_attention:.4f} -> {new_row['weighted_attention']:.4f} "
                              f"({'+'if new_row['weighted_attention'] > old_feature.weighted_attention else ''}{(new_row['weighted_attention'] - old_feature.weighted_attention):.4f})")
                        print(f"      bullish_attention:   {old_feature.bullish_attention:.4f} -> {new_row['bullish_attention']:.4f} "
                              f"({'+'if new_row['bullish_attention'] > old_feature.bullish_attention else ''}{(new_row['bullish_attention'] - old_feature.bullish_attention):.4f})")
                        print(f"      bearish_attention:   {old_feature.bearish_attention:.4f} -> {new_row['bearish_attention']:.4f} "
                              f"({'+'if new_row['bearish_attention'] > old_feature.bearish_attention else ''}{(new_row['bearish_attention'] - old_feature.bearish_attention):.4f})")
                        print(f"      composite_score:     {old_feature.composite_attention_score:.4f} -> {new_row['composite_attention_score']:.4f} "
                              f"({'+'if new_row['composite_attention_score'] > old_feature.composite_attention_score else ''}{(new_row['composite_attention_score'] - old_feature.composite_attention_score):.4f})")
                        
                        if shown_count >= 5:
                            break
        
        return True
        
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        session.rollback()
        return False
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description='重新计算因权重更新而受影响的注意力特征'
    )
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='要更新的 symbols（空格分隔），不指定则更新所有活跃 symbols'
    )
    parser.add_argument(
        '--timeframe',
        default='1d',
        choices=['1d', '4h'],
        help='时间粒度（默认: 1d）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式，不实际更新数据库'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("重新计算注意力特征（权重更新后）")
    print("=" * 60)
    
    if args.dry_run:
        print("⚠️  DRY RUN 模式 - 不会修改数据库")
    
    # 获取要更新的 symbols
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    symbols = get_symbols_to_update(session, args.symbols)
    session.close()
    
    if not symbols:
        print("❌ 未找到要更新的 symbols")
        return 1
    
    print(f"\n将处理 {len(symbols)} 个 symbols: {', '.join(symbols)}")
    print(f"时间粒度: {args.timeframe}")
    
    if not args.dry_run:
        confirm = input("\n确认开始更新？(y/N): ")
        if confirm.lower() != 'y':
            print("已取消")
            return 0
    
    # 处理每个 symbol
    success_count = 0
    fail_count = 0
    
    for symbol in symbols:
        if recompute_features_for_symbol(symbol, args.timeframe, args.dry_run):
            success_count += 1
        else:
            fail_count += 1
    
    # 总结
    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")
    
    if args.dry_run:
        print("\n💡 这是试运行模式。要实际更新数据库，请移除 --dry-run 参数")
    
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
