#!/usr/bin/env python3
"""
数据库迁移脚本：为 attention_features 表添加 timeframe 支持

本脚本用于升级旧的 attention_features 表结构，以支持多时间频率的注意力特征存储。

升级内容：
1. 添加 timeframe 列（如果不存在）
2. 将现有记录的 timeframe 设置为 'D'（日级）
3. 重建唯一约束以包含 timeframe（仅 PostgreSQL）

对于 SQLite 数据库，由于其不支持修改约束的限制，需要重建整个表。
本脚本提供两种模式：
- 安全模式（默认）：仅添加列和更新数据，不修改约束
- 完整模式（--full）：重建表结构（可能需要较长时间）

使用方法：
    python scripts/migrate_attention_timeframe.py [--full] [--dry-run]

参数：
    --full    : 完整迁移，包括重建表结构（SQLite 需要）
    --dry-run : 仅显示将要执行的操作，不实际执行
"""
import argparse
import logging
import sys
from pathlib import Path

# 确保项目根目录可被导入
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import inspect, text
from src.config.settings import DATABASE_URL
from src.database.models import get_engine, init_database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description='迁移 attention_features 表以支持 timeframe',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='完整迁移，包括重建表结构（SQLite 需要此选项才能修改唯一约束）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示将要执行的操作，不实际执行'
    )
    return parser.parse_args()


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    inspector = inspect(engine)
    columns = {col['name'] for col in inspector.get_columns(table_name)}
    return column_name in columns


def migrate_sqlite_safe(engine, dry_run: bool = False):
    """SQLite 安全迁移：仅添加列和更新数据"""
    logger.info("Performing SQLite safe migration (add column only)")
    
    if not check_column_exists(engine, 'attention_features', 'timeframe'):
        sql = "ALTER TABLE attention_features ADD COLUMN timeframe TEXT DEFAULT 'D'"
        logger.info("SQL: %s", sql)
        if not dry_run:
            with engine.begin() as conn:
                conn.execute(text(sql))
            logger.info("Added timeframe column")
        else:
            logger.info("DRY RUN: Would add timeframe column")
    else:
        logger.info("Column timeframe already exists")
    
    # 更新现有记录
    sql = "UPDATE attention_features SET timeframe = 'D' WHERE timeframe IS NULL"
    logger.info("SQL: %s", sql)
    if not dry_run:
        with engine.begin() as conn:
            result = conn.execute(text(sql))
            logger.info("Updated %d records with timeframe='D'", result.rowcount)
    else:
        logger.info("DRY RUN: Would update NULL timeframe records to 'D'")
    
    logger.warning(
        "NOTE: SQLite does not support modifying unique constraints. "
        "To fully support 4H data storage with separate entries for same datetime, "
        "use --full option to rebuild the table."
    )


def migrate_sqlite_full(engine, dry_run: bool = False):
    """SQLite 完整迁移：重建表结构"""
    logger.info("Performing SQLite full migration (rebuild table)")
    
    statements = [
        # 1. 创建新表
        """
        CREATE TABLE IF NOT EXISTS attention_features_new (
            id INTEGER PRIMARY KEY,
            symbol_id INTEGER NOT NULL,
            datetime DATETIME NOT NULL,
            timeframe TEXT NOT NULL DEFAULT 'D',
            news_count INTEGER NOT NULL DEFAULT 0,
            attention_score FLOAT NOT NULL DEFAULT 0.0,
            weighted_attention FLOAT DEFAULT 0.0,
            bullish_attention FLOAT DEFAULT 0.0,
            bearish_attention FLOAT DEFAULT 0.0,
            event_intensity INTEGER DEFAULT 0,
            news_channel_score FLOAT DEFAULT 0.0,
            google_trend_value FLOAT DEFAULT 0.0,
            google_trend_zscore FLOAT DEFAULT 0.0,
            google_trend_change_7d FLOAT DEFAULT 0.0,
            google_trend_change_30d FLOAT DEFAULT 0.0,
            twitter_volume FLOAT DEFAULT 0.0,
            twitter_volume_zscore FLOAT DEFAULT 0.0,
            twitter_volume_change_7d FLOAT DEFAULT 0.0,
            composite_attention_score FLOAT DEFAULT 0.0,
            composite_attention_zscore FLOAT DEFAULT 0.0,
            composite_attention_spike_flag INTEGER DEFAULT 0,
            FOREIGN KEY (symbol_id) REFERENCES symbols (id),
            UNIQUE (symbol_id, datetime, timeframe)
        )
        """,
        # 2. 复制数据
        """
        INSERT INTO attention_features_new 
        SELECT id, symbol_id, datetime, COALESCE(timeframe, 'D'),
               news_count, attention_score, weighted_attention, 
               bullish_attention, bearish_attention, event_intensity,
               news_channel_score, google_trend_value, google_trend_zscore,
               google_trend_change_7d, google_trend_change_30d,
               twitter_volume, twitter_volume_zscore, twitter_volume_change_7d,
               composite_attention_score, composite_attention_zscore,
               composite_attention_spike_flag
        FROM attention_features
        """,
        # 3. 删除旧表
        "DROP TABLE attention_features",
        # 4. 重命名新表
        "ALTER TABLE attention_features_new RENAME TO attention_features",
        # 5. 重建索引
        "CREATE INDEX IF NOT EXISTS ix_attention_symbol_datetime_tf ON attention_features (symbol_id, datetime, timeframe)",
        "CREATE INDEX IF NOT EXISTS ix_attention_symbol_id ON attention_features (symbol_id)",
    ]
    
    for sql in statements:
        sql = sql.strip()
        logger.info("SQL: %s", sql[:100] + "..." if len(sql) > 100 else sql)
        if not dry_run:
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql))
            except Exception as e:
                logger.error("Failed to execute SQL: %s", e)
                raise
    
    if dry_run:
        logger.info("DRY RUN: Would rebuild attention_features table with new schema")
    else:
        logger.info("Successfully rebuilt attention_features table with new unique constraint")


def migrate_postgres(engine, dry_run: bool = False):
    """PostgreSQL 迁移"""
    logger.info("Performing PostgreSQL migration")
    
    statements = []
    
    # 1. 添加 timeframe 列（如果不存在）
    if not check_column_exists(engine, 'attention_features', 'timeframe'):
        statements.append(
            "ALTER TABLE attention_features ADD COLUMN timeframe TEXT DEFAULT 'D'"
        )
    
    # 2. 更新现有记录
    statements.append(
        "UPDATE attention_features SET timeframe = 'D' WHERE timeframe IS NULL"
    )
    
    # 3. 删除旧唯一约束（如果存在）
    statements.append(
        "ALTER TABLE attention_features DROP CONSTRAINT IF EXISTS uq_attention_symbol_dt"
    )
    
    # 4. 添加新唯一约束
    statements.append(
        "ALTER TABLE attention_features ADD CONSTRAINT uq_attention_symbol_dt_tf "
        "UNIQUE (symbol_id, datetime, timeframe)"
    )
    
    for sql in statements:
        logger.info("SQL: %s", sql)
        if not dry_run:
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql))
            except Exception as e:
                logger.warning("SQL execution warning: %s", e)
    
    if dry_run:
        logger.info("DRY RUN: Would perform PostgreSQL migration")
    else:
        logger.info("Successfully migrated PostgreSQL database")


def main():
    args = parse_args()
    
    logger.info("=" * 70)
    logger.info("Attention Features Table Migration: Adding timeframe support")
    logger.info("Database: %s", DATABASE_URL[:50] + "..." if len(DATABASE_URL) > 50 else DATABASE_URL)
    logger.info("Mode: %s", "FULL" if args.full else "SAFE")
    if args.dry_run:
        logger.info("DRY RUN MODE: No changes will be made")
    logger.info("=" * 70)
    
    # 初始化数据库引擎
    engine = get_engine()
    
    # 确保表存在
    init_database()
    
    # 检测数据库类型
    is_sqlite = DATABASE_URL.startswith("sqlite")
    
    try:
        if is_sqlite:
            if args.full:
                migrate_sqlite_full(engine, args.dry_run)
            else:
                migrate_sqlite_safe(engine, args.dry_run)
        else:
            migrate_postgres(engine, args.dry_run)
        
        logger.info("=" * 70)
        logger.info("Migration completed successfully!")
        logger.info("=" * 70)
        return 0
        
    except Exception as e:
        logger.error("Migration failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
