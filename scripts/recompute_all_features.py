#!/usr/bin/env python3
"""
全量重新计算数据库特征

完整更新 AttentionFeature 表的所有字段，包括：
1. 基础注意力特征 (news_count, attention_score, weighted_attention, etc.)
2. 事件检测 (detected_events)
3. 价格快照 (close_price, open_price, etc.)
4. 滚动收益率 (return_1d, return_7d, etc.)
5. 滚动波动率 (volatility_7d, etc.)
6. 成交量统计 (volume_zscore_7d, etc.)
7. 价格极值 (high_30d, low_30d, etc.)
8. State Features (feat_ret_zscore_7d, etc.)
9. Forward Returns (forward_return_3d, etc.)
10. 最大回撤 (max_drawdown_7d, etc.)

使用方法:
    python scripts/recompute_all_features.py [--symbol ZEC] [--skip-news] [--skip-snapshots]

参数:
    --symbol: 指定币种，默认处理所有活跃币种
    --skip-news: 跳过新闻特征更新
    --skip-snapshots: 跳过状态快照更新
    --force-gt: 强制重新获取 Google Trends 数据
"""
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.db_storage import get_db
from src.database.models import News, Symbol, get_session
from src.features.news_features import sentiment_score, extract_tags, relevance_flag
from src.services.attention_service import AttentionService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def recompute_news_scores(batch_size: int = 1000):
    """
    重新计算新闻的情感分数和标签
    
    更新 News 表的:
    - sentiment_score: 情感分数
    - tags: 关键词标签
    - relevance: 相关性
    """
    logger.info("=" * 60)
    logger.info("步骤 1/3: 重新计算新闻特征 (Sentiment & Tags)")
    logger.info("=" * 60)
    
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
            
            # 3. 更新 Relevance
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
        if processed % 5000 == 0 or processed == total:
            logger.info(f"进度: {processed}/{total} (已更新 {updated})")
        
    session.close()
    logger.info(f"✅ 新闻特征更新完成！共更新 {updated} 条记录")
    return updated


def recompute_attention_features(symbol_filter: str = None, force_google_trends: bool = False):
    """
    重新计算所有币种的注意力特征
    
    使用 AttentionService.update_attention_features() 完整计算：
    - 基础注意力特征 (17个字段)
    - 事件检测 (detected_events)
    - 预计算字段 (价格派生指标、State Features、Forward Returns 等)
    
    Args:
        symbol_filter: 指定币种，None 表示所有活跃币种
        force_google_trends: 是否强制重新获取 Google Trends
    """
    logger.info("=" * 60)
    logger.info("步骤 2/3: 重新计算 Attention Features (完整)")
    logger.info("=" * 60)
    
    db = get_db()
    session = get_session(db.engine)
    
    # 获取要处理的币种
    query = session.query(Symbol).filter(Symbol.is_active == True)
    if symbol_filter:
        query = query.filter(Symbol.symbol == symbol_filter.upper())
    
    symbols = query.all()
    logger.info(f"待处理币种数: {len(symbols)}")
    
    if not symbols:
        logger.warning("未找到需要处理的币种")
        return 0
    
    session.close()
    
    success_count = 0
    fail_count = 0
    
    for idx, symbol_obj in enumerate(symbols, 1):
        symbol = symbol_obj.symbol
        logger.info(f"\n[{idx}/{len(symbols)}] 处理 {symbol}...")
        
        try:
            # 使用 AttentionService 完整计算
            # 这会调用:
            # 1. calculate_composite_attention() - 基础注意力特征
            # 2. detect_events_per_row() - 事件检测
            # 3. compute_all_precomputed_fields() - 价格派生指标、State Features、Forward Returns
            result_df = AttentionService.update_attention_features(
                symbol=symbol,
                freq='D',
                save_to_db=True
            )
            
            if result_df is not None and not result_df.empty:
                # 检查关键字段是否存在
                key_fields = [
                    'news_count', 'attention_score', 'weighted_attention',
                    'detected_events', 'close_price', 'return_7d',
                    'volatility_7d', 'feat_ret_zscore_7d'
                ]
                missing = [f for f in key_fields if f not in result_df.columns]
                
                if missing:
                    logger.warning(f"  ⚠️ {symbol}: 缺少字段 {missing}")
                
                # 统计事件
                if 'detected_events' in result_df.columns:
                    events_count = result_df['detected_events'].notna().sum()
                    logger.info(f"  ✅ {symbol}: {len(result_df)} 条记录, {events_count} 条有事件")
                else:
                    logger.info(f"  ✅ {symbol}: {len(result_df)} 条记录")
                
                success_count += 1
            else:
                logger.warning(f"  ⚠️ {symbol}: 无数据返回")
                fail_count += 1
                
        except Exception as e:
            logger.error(f"  ❌ {symbol} 失败: {e}")
            fail_count += 1
    
    logger.info(f"\n✅ Attention Features 更新完成！成功 {success_count}, 失败 {fail_count}")
    return success_count


def recompute_state_snapshots(symbol_filter: str = None):
    """
    重新计算状态快照
    
    调用 recompute_state_snapshots.py 的逻辑
    """
    logger.info("=" * 60)
    logger.info("步骤 3/3: 重新计算 State Snapshots")
    logger.info("=" * 60)
    
    try:
        from src.database.models import Symbol, AttentionFeature
        from src.research.state_snapshot import compute_state_snapshot
        from src.database.models import StateSnapshot as SnapshotModel
        from src.config.settings import DATABASE_URL
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import json
        
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # 获取活跃币种
        query = session.query(Symbol).filter(Symbol.is_active == True)
        if symbol_filter:
            query = query.filter(Symbol.symbol == symbol_filter.upper())
        symbols = [s.symbol for s in query.all()]
        
        if not symbols:
            logger.warning("未找到活跃币种")
            return 0
        
        logger.info(f"将为 {len(symbols)} 个币种计算状态快照...")
        
        updated = 0
        
        for symbol in symbols:
            sym_row = session.query(Symbol).filter(Symbol.symbol == symbol).first()
            if not sym_row:
                continue
            
            # 获取所有特征时间点
            rows = (
                session.query(AttentionFeature.datetime)
                .filter(AttentionFeature.symbol_id == sym_row.id)
                .filter(AttentionFeature.timeframe == 'D')
                .order_by(AttentionFeature.datetime.asc())
                .all()
            )
            datetimes = [r[0] for r in rows]
            
            if not datetimes:
                logger.warning(f"  ⚠️ {symbol} 无特征数据，跳过")
                continue
            
            count = 0
            batch = 0
            
            for dt in datetimes:
                snap = compute_state_snapshot(
                    symbol=symbol,
                    as_of=dt,
                    timeframe='1d',
                    window_days=30,
                )
                if not snap:
                    continue
                
                # Upsert
                existing = (
                    session.query(SnapshotModel)
                    .filter(
                        SnapshotModel.symbol_id == sym_row.id,
                        SnapshotModel.datetime == snap.as_of,
                        SnapshotModel.timeframe == '1d',
                        SnapshotModel.window_days == 30,
                    )
                    .first()
                )
                
                if existing:
                    existing.features = json.dumps(snap.features, ensure_ascii=False)
                    existing.raw_stats = json.dumps(snap.raw_stats, ensure_ascii=False) if snap.raw_stats else None
                else:
                    sm = SnapshotModel.from_computed(
                        symbol_id=sym_row.id,
                        dt=snap.as_of,
                        timeframe='1d',
                        features=snap.features,
                        raw_stats=snap.raw_stats,
                        window_days=30,
                    )
                    session.add(sm)
                
                updated += 1
                count += 1
                batch += 1
                
                if batch % 500 == 0:
                    session.commit()
                    batch = 0
            
            session.commit()
            logger.info(f"  ✅ {symbol}: 更新 {count} 条快照")
        
        session.close()
        logger.info(f"\n✅ State Snapshots 更新完成！共 {updated} 条")
        return updated
        
    except Exception as e:
        logger.error(f"State Snapshots 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    parser = argparse.ArgumentParser(description='全量重新计算数据库特征')
    parser.add_argument('--symbol', type=str, help='指定币种（默认所有活跃币种）')
    parser.add_argument('--skip-news', action='store_true', help='跳过新闻特征更新')
    parser.add_argument('--skip-snapshots', action='store_true', help='跳过状态快照更新')
    parser.add_argument('--force-gt', action='store_true', help='强制重新获取 Google Trends')
    args = parser.parse_args()
    
    print("\n" + "=" * 60)
    print("全量重新计算数据库特征")
    print("=" * 60)
    print(f"时间: {datetime.now(timezone.utc).isoformat()}")
    print(f"币种: {args.symbol or '所有活跃币种'}")
    print(f"跳过新闻: {args.skip_news}")
    print(f"跳过快照: {args.skip_snapshots}")
    print("=" * 60)
    
    # 1. 更新新闻特征
    if not args.skip_news:
        recompute_news_scores()
    else:
        logger.info("跳过新闻特征更新")
    
    # 2. 更新注意力特征（完整计算）
    recompute_attention_features(
        symbol_filter=args.symbol,
        force_google_trends=args.force_gt
    )
    
    # 3. 更新状态快照
    if not args.skip_snapshots:
        recompute_state_snapshots(symbol_filter=args.symbol)
    else:
        logger.info("跳过状态快照更新")
    
    print("\n" + "=" * 60)
    print("✅ 全量重新计算完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
