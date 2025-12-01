#!/usr/bin/env python3
"""
Database Migration: Add Precomputed Features to AttentionFeature Table

本脚本为 AttentionFeature 表添加预计算特征字段，支持 SQLite 和 PostgreSQL。

新增字段分类：
1. 价格快照: close_price, open_price, high_price, low_price, volume
2. 滚动收益率: return_1d, return_7d, return_30d, return_60d
3. 滚动波动率: volatility_7d, volatility_30d, volatility_60d
4. 其他滚动统计: volume_zscore_7d/30d, high/low_30d/60d
5. State Features: feat_ret_zscore_*, feat_vol_zscore_*, feat_att_*, feat_sentiment_*
6. Forward Returns: forward_return_3d/7d/30d, max_drawdown_7d/30d

使用方法:
    python scripts/migrate_add_precomputed_fields.py
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
from sqlalchemy import create_engine, text, inspect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 新增字段定义: (column_name, sql_type_sqlite, sql_type_postgresql)
NEW_COLUMNS = [
    # 价格快照
    ('close_price', 'REAL', 'DOUBLE PRECISION'),
    ('open_price', 'REAL', 'DOUBLE PRECISION'),
    ('high_price', 'REAL', 'DOUBLE PRECISION'),
    ('low_price', 'REAL', 'DOUBLE PRECISION'),
    ('volume', 'REAL', 'DOUBLE PRECISION'),
    
    # 滚动收益率
    ('return_1d', 'REAL', 'DOUBLE PRECISION'),
    ('return_7d', 'REAL', 'DOUBLE PRECISION'),
    ('return_30d', 'REAL', 'DOUBLE PRECISION'),
    ('return_60d', 'REAL', 'DOUBLE PRECISION'),
    
    # 滚动波动率
    ('volatility_7d', 'REAL', 'DOUBLE PRECISION'),
    ('volatility_30d', 'REAL', 'DOUBLE PRECISION'),
    ('volatility_60d', 'REAL', 'DOUBLE PRECISION'),
    
    # 其他滚动统计
    ('volume_zscore_7d', 'REAL', 'DOUBLE PRECISION'),
    ('volume_zscore_30d', 'REAL', 'DOUBLE PRECISION'),
    ('high_30d', 'REAL', 'DOUBLE PRECISION'),
    ('low_30d', 'REAL', 'DOUBLE PRECISION'),
    ('high_60d', 'REAL', 'DOUBLE PRECISION'),
    ('low_60d', 'REAL', 'DOUBLE PRECISION'),
    
    # State Features (规范化)
    ('feat_ret_zscore_7d', 'REAL', 'DOUBLE PRECISION'),
    ('feat_ret_zscore_30d', 'REAL', 'DOUBLE PRECISION'),
    ('feat_ret_zscore_60d', 'REAL', 'DOUBLE PRECISION'),
    ('feat_vol_zscore_7d', 'REAL', 'DOUBLE PRECISION'),
    ('feat_vol_zscore_30d', 'REAL', 'DOUBLE PRECISION'),
    ('feat_vol_zscore_60d', 'REAL', 'DOUBLE PRECISION'),
    ('feat_att_trend_7d', 'REAL', 'DOUBLE PRECISION'),
    ('feat_att_news_share', 'REAL', 'DOUBLE PRECISION'),
    ('feat_att_google_share', 'REAL', 'DOUBLE PRECISION'),
    ('feat_att_twitter_share', 'REAL', 'DOUBLE PRECISION'),
    ('feat_bullish_minus_bearish', 'REAL', 'DOUBLE PRECISION'),
    ('feat_sentiment_mean', 'REAL', 'DOUBLE PRECISION'),
    
    # Forward Returns (仅历史数据)
    ('forward_return_3d', 'REAL', 'DOUBLE PRECISION'),
    ('forward_return_7d', 'REAL', 'DOUBLE PRECISION'),
    ('forward_return_30d', 'REAL', 'DOUBLE PRECISION'),
    ('max_drawdown_7d', 'REAL', 'DOUBLE PRECISION'),
    ('max_drawdown_30d', 'REAL', 'DOUBLE PRECISION'),
]


def get_existing_columns(engine, table_name: str) -> set:
    """获取表中已存在的列名"""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return {col['name'] for col in columns}


def add_columns_sqlite(engine, table_name: str, columns_to_add: list):
    """SQLite: 逐个添加列"""
    with engine.connect() as conn:
        for col_name, sql_type, _ in columns_to_add:
            try:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sql_type}"
                conn.execute(text(sql))
                logger.info(f"  ✓ 添加列: {col_name}")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug(f"  - 列已存在: {col_name}")
                else:
                    logger.error(f"  ✗ 添加列失败 {col_name}: {e}")
        conn.commit()


def add_columns_postgresql(engine, table_name: str, columns_to_add: list):
    """PostgreSQL: 批量添加列"""
    with engine.connect() as conn:
        for col_name, _, sql_type in columns_to_add:
            try:
                sql = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {sql_type}"
                conn.execute(text(sql))
                logger.info(f"  ✓ 添加列: {col_name}")
            except Exception as e:
                logger.error(f"  ✗ 添加列失败 {col_name}: {e}")
        conn.commit()


def add_vector_column_postgresql(engine, table_name: str, vector_dim: int = 12):
    """PostgreSQL: 添加 pgvector 列"""
    with engine.connect() as conn:
        try:
            # 检查 pgvector 扩展
            result = conn.execute(text(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ))
            if not result.scalar():
                logger.warning("  pgvector 扩展未安装，跳过 feature_vector 列")
                return False
            
            # 添加向量列
            sql = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS feature_vector vector({vector_dim})"
            conn.execute(text(sql))
            conn.commit()
            
            # 创建 HNSW 索引（用于快速相似度搜索）
            index_sql = f"""
                CREATE INDEX IF NOT EXISTS ix_{table_name}_feature_vector 
                ON {table_name} 
                USING hnsw (feature_vector vector_cosine_ops)
            """
            conn.execute(text(index_sql))
            conn.commit()
            
            logger.info(f"  ✓ 添加向量列: feature_vector({vector_dim})")
            logger.info(f"  ✓ 创建 HNSW 索引: ix_{table_name}_feature_vector")
            return True
            
        except Exception as e:
            logger.error(f"  ✗ 添加向量列失败: {e}")
            return False


def migrate_attention_features_table():
    """迁移 attention_features 表"""
    from src.config.settings import DATABASE_URL
    
    engine = create_engine(DATABASE_URL)
    is_postgresql = DATABASE_URL.startswith("postgresql")
    table_name = "attention_features"
    
    logger.info(f"\n{'='*60}")
    logger.info(f"迁移表: {table_name}")
    logger.info(f"数据库类型: {'PostgreSQL' if is_postgresql else 'SQLite'}")
    logger.info(f"{'='*60}")
    
    # 获取已存在的列
    existing_columns = get_existing_columns(engine, table_name)
    logger.info(f"现有列数: {len(existing_columns)}")
    
    # 筛选需要添加的列
    columns_to_add = [
        (name, sqlite_type, pg_type) 
        for name, sqlite_type, pg_type in NEW_COLUMNS 
        if name not in existing_columns
    ]
    
    if not columns_to_add:
        logger.info("所有字段已存在，无需迁移")
        return True
    
    logger.info(f"需要添加 {len(columns_to_add)} 个新列...")
    
    # 添加列
    if is_postgresql:
        add_columns_postgresql(engine, table_name, columns_to_add)
        # 添加向量列
        add_vector_column_postgresql(engine, table_name, vector_dim=12)
    else:
        add_columns_sqlite(engine, table_name, columns_to_add)
    
    # 验证
    new_columns = get_existing_columns(engine, table_name)
    added_count = len(new_columns) - len(existing_columns)
    logger.info(f"\n迁移完成: 添加了 {added_count} 个新列")
    logger.info(f"当前总列数: {len(new_columns)}")
    
    return True


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("数据库迁移: 添加预计算特征字段")
    print("=" * 60)
    
    try:
        migrate_attention_features_table()
        
        print("\n" + "=" * 60)
        print("迁移成功!")
        print("=" * 60)
        print("\n下一步:")
        print("1. 运行 python scripts/backfill_precomputed_features.py 填充历史数据")
        print("2. 重启服务: ./scripts/dev.sh")
        
        return 0
        
    except Exception as e:
        logger.error(f"迁移失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
