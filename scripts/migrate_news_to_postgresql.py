#!/usr/bin/env python3
"""
迁移新闻数据从 SQLite 到 PostgreSQL

将 crypto_news.db 中的新闻数据迁移到主 PostgreSQL 数据库的 news 表。
迁移后，新闻将与其他数据（价格、Attention 等）在同一个数据库中。
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import os
import logging
from datetime import datetime

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migrate_news():
    """迁移新闻数据"""
    from src.config.settings import DATA_DIR
    
    # 源：SQLite 新闻数据库
    sqlite_path = DATA_DIR / "crypto_news.db"
    if not sqlite_path.exists():
        logger.error(f"SQLite 新闻数据库不存在: {sqlite_path}")
        return False
    
    sqlite_url = f"sqlite:///{sqlite_path}"
    sqlite_engine = create_engine(sqlite_url)
    
    # 目标：PostgreSQL
    pg_url = os.getenv("DATABASE_URL")
    if not pg_url or pg_url.startswith("sqlite"):
        logger.error("DATABASE_URL 必须是 PostgreSQL 连接字符串")
        logger.error("请确保 .env 中配置了: DATABASE_URL=\"postgresql://localhost/crypto_attention\"")
        return False
    
    logger.info(f"源数据库: {sqlite_url}")
    logger.info(f"目标数据库: {pg_url[:50]}...")
    
    pg_engine = create_engine(pg_url, pool_pre_ping=True)
    
    # 检查源表
    sqlite_inspector = inspect(sqlite_engine)
    if 'news' not in sqlite_inspector.get_table_names():
        logger.error("SQLite 中没有 news 表")
        return False
    
    # 获取源表列信息
    source_columns = [col['name'] for col in sqlite_inspector.get_columns('news')]
    logger.info(f"源表列: {source_columns}")
    
    # 检查目标表
    pg_inspector = inspect(pg_engine)
    if 'news' not in pg_inspector.get_table_names():
        logger.error("PostgreSQL 中没有 news 表，请先运行主迁移脚本")
        return False
    
    target_columns = [col['name'] for col in pg_inspector.get_columns('news')]
    logger.info(f"目标表列: {target_columns}")
    
    # 只迁移两边都有的列
    common_columns = [c for c in source_columns if c in target_columns]
    logger.info(f"共同列: {common_columns}")
    
    # 读取所有新闻
    columns_str = ', '.join([f'"{c}"' for c in common_columns])
    
    with sqlite_engine.connect() as conn:
        result = conn.execute(text(f"SELECT {columns_str} FROM news"))
        rows = result.fetchall()
    
    total = len(rows)
    logger.info(f"从 SQLite 读取 {total} 条新闻")
    
    if total == 0:
        logger.warning("没有新闻数据需要迁移")
        return True
    
    # 获取 PostgreSQL 中已有的 URL（用于去重）
    PgSession = sessionmaker(bind=pg_engine)
    pg_session = PgSession()
    
    try:
        existing_urls = set()
        result = pg_session.execute(text("SELECT url FROM news"))
        for row in result:
            existing_urls.add(row[0])
        logger.info(f"PostgreSQL 中已有 {len(existing_urls)} 条新闻")
        
        # 准备插入
        placeholders = ', '.join([f':{c}' for c in common_columns])
        insert_sql = f'INSERT INTO news ({columns_str}) VALUES ({placeholders})'
        
        migrated = 0
        skipped = 0
        errors = 0
        
        for i, row in enumerate(rows):
            data = dict(zip(common_columns, row))
            
            # 跳过已存在的
            if data.get('url') in existing_urls:
                skipped += 1
                continue
            
            try:
                # 处理空字符串
                for key, value in list(data.items()):
                    if isinstance(value, str) and value == '':
                        data[key] = None
                
                pg_session.execute(text(insert_sql), data)
                migrated += 1
                
                # 批量提交
                if migrated % 500 == 0:
                    pg_session.commit()
                    logger.info(f"进度: {i+1}/{total}, 已迁移 {migrated}, 跳过 {skipped}")
                    
            except Exception as e:
                pg_session.rollback()
                errors += 1
                if errors <= 3:
                    logger.warning(f"插入失败: {e}")
        
        # 最终提交
        pg_session.commit()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"迁移完成!")
        logger.info(f"  总计: {total}")
        logger.info(f"  已迁移: {migrated}")
        logger.info(f"  跳过(已存在): {skipped}")
        logger.info(f"  错误: {errors}")
        logger.info(f"{'='*60}")
        
        # 验证
        result = pg_session.execute(text("SELECT COUNT(*) FROM news"))
        final_count = result.scalar()
        logger.info(f"PostgreSQL news 表现有 {final_count} 条记录")
        
        return True
        
    finally:
        pg_session.close()


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("新闻数据迁移: SQLite → PostgreSQL")
    print("=" * 60 + "\n")
    
    success = migrate_news()
    
    if success:
        print("\n✅ 迁移成功!")
        print("\n下一步:")
        print("1. 在 .env 中添加: NEWS_DATABASE_URL=\"postgresql://localhost/crypto_attention\"")
        print("2. 重启服务验证新闻 API")
        print("3. 确认无误后可删除 data/crypto_news.db")
    else:
        print("\n❌ 迁移失败，请检查错误信息")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
