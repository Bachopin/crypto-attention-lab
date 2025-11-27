#!/usr/bin/env python3
"""
数据库迁移工具：从 SQLite 迁移到 PostgreSQL
使用方法：
1. 确保 PostgreSQL 已启动并创建了数据库
2. 设置环境变量 PG_DATABASE_URL
3. 运行此脚本
"""
import os
import sys
from pathlib import Path
import logging
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import DATABASE_URL as SQLITE_URL
from src.database.models import Base, Symbol, News, Price, AttentionFeature

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_data(target_db_url: str):
    if not target_db_url:
        logger.error("Target database URL is empty!")
        return
    
    if target_db_url.startswith("sqlite"):
        logger.error("Target database cannot be SQLite (we are migrating FROM SQLite)")
        return

    logger.info(f"Source (SQLite): {SQLITE_URL}")
    logger.info(f"Target (Postgres): {target_db_url}")

    # 1. 连接源数据库 (SQLite)
    src_engine = create_engine(SQLITE_URL)
    SrcSession = sessionmaker(bind=src_engine)
    src_session = SrcSession()

    # 2. 连接目标数据库 (PostgreSQL)
    tgt_engine = create_engine(target_db_url)
    TgtSession = sessionmaker(bind=tgt_engine)
    tgt_session = TgtSession()

    # 3. 在目标数据库创建表
    logger.info("Creating tables in target database...")
    Base.metadata.create_all(tgt_engine)

    # 4. 迁移数据
    try:
        # --- 迁移 Symbols ---
        symbols = src_session.query(Symbol).all()
        logger.info(f"Migrating {len(symbols)} symbols...")
        for item in symbols:
            src_session.expunge(item) # Detach from source session
            tgt_session.merge(item)   # Merge into target session
        tgt_session.commit()

        # --- 迁移 News ---
        news_items = src_session.query(News).all()
        logger.info(f"Migrating {len(news_items)} news items...")
        # 批量插入以提高性能
        tgt_session.bulk_save_objects([
            News(
                timestamp=n.timestamp, datetime=n.datetime, title=n.title,
                source=n.source, url=n.url, symbols=n.symbols, relevance=n.relevance,
                source_weight=n.source_weight, sentiment_score=n.sentiment_score, tags=n.tags,
                created_at=n.created_at
            ) for n in news_items
        ])
        tgt_session.commit()

        # --- 迁移 Prices ---
        # 需要重新关联 symbol_id，因为目标库的 ID 可能不同（虽然 merge 应该保留了 ID，但安全起见）
        # 这里假设 ID 保持一致，因为我们是全量迁移
        prices = src_session.query(Price).all()
        logger.info(f"Migrating {len(prices)} price records...")
        tgt_session.bulk_save_objects([
            Price(
                symbol_id=p.symbol_id, timeframe=p.timeframe, timestamp=p.timestamp,
                datetime=p.datetime, open=p.open, high=p.high, low=p.low,
                close=p.close, volume=p.volume
            ) for p in prices
        ])
        tgt_session.commit()

        # --- 迁移 AttentionFeatures ---
        features = src_session.query(AttentionFeature).all()
        logger.info(f"Migrating {len(features)} attention features...")
        tgt_session.bulk_save_objects([
            AttentionFeature(
                symbol_id=f.symbol_id, datetime=f.datetime, news_count=f.news_count,
                attention_score=f.attention_score, weighted_attention=f.weighted_attention,
                bullish_attention=f.bullish_attention, bearish_attention=f.bearish_attention,
                event_intensity=f.event_intensity
            ) for f in features
        ])
        tgt_session.commit()

        logger.info("✅ Migration completed successfully!")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        tgt_session.rollback()
    finally:
        src_session.close()
        tgt_session.close()

if __name__ == "__main__":
    # 从命令行参数或环境变量获取目标 URL
    target_url = os.getenv("PG_DATABASE_URL")
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    
    if not target_url:
        print("Usage: python scripts/migrate_to_postgres.py <postgres_url>")
        print("   OR: export PG_DATABASE_URL=... && python scripts/migrate_to_postgres.py")
        sys.exit(1)
        
    migrate_data(target_url)
