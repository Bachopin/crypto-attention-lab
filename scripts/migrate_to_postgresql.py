#!/usr/bin/env python3
"""
PostgreSQL Migration Script

本脚本用于将数据从 SQLite 迁移到 PostgreSQL，并设置 pgvector 扩展。

使用方法:
1. 安装 PostgreSQL 和 pgvector 扩展
2. 创建数据库: createdb crypto_attention
3. 设置环境变量: export DATABASE_URL="postgresql://user:pass@localhost:5432/crypto_attention"
4. 运行迁移: python scripts/migrate_to_postgresql.py

注意:
- 迁移前请备份 SQLite 数据库
- 迁移后需要运行 scripts/backfill_precomputed_features.py 填充新字段
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_postgresql_connection(pg_url: str) -> bool:
    """检查 PostgreSQL 连接"""
    try:
        engine = create_engine(pg_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"PostgreSQL 连接成功: {version[:50]}...")
            return True
    except Exception as e:
        logger.error(f"PostgreSQL 连接失败: {e}")
        return False


def setup_pgvector(pg_url: str) -> bool:
    """设置 pgvector 扩展"""
    try:
        engine = create_engine(pg_url)
        with engine.connect() as conn:
            # 检查扩展是否已安装
            result = conn.execute(text(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            ))
            exists = result.scalar()
            
            if not exists:
                logger.info("安装 pgvector 扩展...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                logger.info("pgvector 扩展安装成功")
            else:
                logger.info("pgvector 扩展已存在")
            
            return True
    except Exception as e:
        logger.error(f"设置 pgvector 失败: {e}")
        logger.info("提示: 请确保已安装 pgvector 扩展")
        logger.info("  macOS: brew install pgvector")
        logger.info("  Ubuntu: apt install postgresql-16-pgvector")
        return False


def convert_datetime_value(value):
    """将 SQLite 的 datetime 字符串转换为 Python datetime 对象"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        if not value or value.strip() == '':
            return None
        # 尝试多种格式
        formats = [
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        logger.warning(f"无法解析日期时间: {value}")
        return None
    return value


def convert_boolean_value(value):
    """将 SQLite 的 0/1 转换为 Python bool"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return bool(value)


def migrate_table_data(sqlite_url: str, pg_url: str, table_name: str, batch_size: int = 1000):
    """迁移单个表的数据"""
    sqlite_engine = create_engine(sqlite_url)
    pg_engine = create_engine(pg_url)
    
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PgSession = sessionmaker(bind=pg_engine)
    
    sqlite_session = SqliteSession()
    pg_session = PgSession()
    
    # 获取目标表的列类型信息
    pg_inspector = inspect(pg_engine)
    pg_columns_info = {}
    try:
        for col in pg_inspector.get_columns(table_name):
            pg_columns_info[col['name']] = str(col['type'])
    except Exception:
        pass
    
    # 判断哪些列是时间戳类型和布尔类型
    datetime_columns = set()
    boolean_columns = set()
    for col_name, col_type in pg_columns_info.items():
        if 'TIMESTAMP' in col_type.upper() or 'DATETIME' in col_type.upper():
            datetime_columns.add(col_name)
        elif 'BOOLEAN' in col_type.upper():
            boolean_columns.add(col_name)
    
    try:
        # 检查源表是否存在
        inspector = inspect(sqlite_engine)
        if table_name not in inspector.get_table_names():
            logger.warning(f"表 {table_name} 在 SQLite 中不存在，跳过")
            return 0
        
        # 获取总行数
        result = sqlite_session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        total_rows = result.scalar()
        
        if total_rows == 0:
            logger.info(f"表 {table_name} 为空，跳过")
            return 0
        
        logger.info(f"开始迁移表 {table_name}: {total_rows} 行 (datetime: {len(datetime_columns)}, bool: {len(boolean_columns)})")
        
        # 获取列信息 - 只使用 PostgreSQL 中存在的列
        sqlite_columns = [col['name'] for col in inspector.get_columns(table_name)]
        pg_table_columns = set(pg_columns_info.keys())
        
        # 只迁移两个数据库都有的列
        columns = [col for col in sqlite_columns if col in pg_table_columns]
        columns_str = ', '.join([f'"{col}"' for col in columns])  # 加引号避免保留字问题
        placeholders = ', '.join([f':{col}' for col in columns])
        
        # 分批读取和插入
        migrated = 0
        offset = 0
        errors = 0
        
        while offset < total_rows:
            # 从 SQLite 读取
            select_cols = ', '.join([f'"{col}"' for col in columns])
            result = sqlite_session.execute(
                text(f'SELECT {select_cols} FROM "{table_name}" LIMIT {batch_size} OFFSET {offset}')
            )
            rows = result.fetchall()
            
            if not rows:
                break
            
            # 转换为字典列表
            data = [dict(zip(columns, row)) for row in rows]
            
            # 插入到 PostgreSQL
            for row_dict in data:
                try:
                    # 处理可能的类型转换问题
                    for key, value in list(row_dict.items()):
                        if isinstance(value, str) and value == '':
                            row_dict[key] = None
                        # 处理日期时间列
                        elif key in datetime_columns:
                            row_dict[key] = convert_datetime_value(value)
                        # 处理布尔列
                        elif key in boolean_columns:
                            row_dict[key] = convert_boolean_value(value)
                    
                    insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'
                    pg_session.execute(text(insert_sql), row_dict)
                    pg_session.commit()
                    migrated += 1
                    
                except Exception as row_e:
                    pg_session.rollback()
                    errors += 1
                    if errors <= 3:  # 只打印前3个错误
                        logger.warning(f"行插入失败: {row_e}")
                        if errors == 3:
                            logger.warning("(后续错误将不再显示)")
            
            if migrated % 10000 == 0 and migrated > 0:
                logger.info(f"  已迁移 {migrated}/{total_rows} 行...")
            
            offset += batch_size
        
        if errors > 0:
            logger.warning(f"表 {table_name} 迁移完成: {migrated} 行成功, {errors} 行失败")
        else:
            logger.info(f"表 {table_name} 迁移完成: {migrated} 行")
        return migrated
        
    finally:
        sqlite_session.close()
        pg_session.close()


def create_tables_in_postgresql(pg_url: str):
    """在 PostgreSQL 中创建所有表"""
    from src.database.models import Base, get_engine
    
    engine = get_engine(pg_url)
    Base.metadata.create_all(engine)
    logger.info("PostgreSQL 表结构创建完成")


def migrate_all_data(sqlite_url: str, pg_url: str):
    """迁移所有表的数据"""
    # 按依赖顺序迁移
    tables_order = [
        'symbols',
        'news',
        'prices',
        'attention_features',
        'google_trends',
        'twitter_volumes',
        'node_attention_features',
        'node_carry_factors',
        'state_snapshots',
        'news_stats',
    ]
    
    total_migrated = 0
    for table in tables_order:
        count = migrate_table_data(sqlite_url, pg_url, table)
        total_migrated += count
    
    logger.info(f"\n总共迁移 {total_migrated} 行数据")
    return total_migrated


def update_sequences(pg_url: str):
    """更新 PostgreSQL 序列值"""
    engine = create_engine(pg_url)
    
    tables = ['symbols', 'news', 'prices', 'attention_features', 'google_trends', 
              'twitter_volumes', 'node_attention_features', 'node_carry_factors',
              'state_snapshots', 'news_stats']
    
    with engine.connect() as conn:
        for table in tables:
            try:
                # 获取当前最大 ID
                result = conn.execute(text(f"SELECT MAX(id) FROM {table}"))
                max_id = result.scalar()
                
                if max_id is not None:
                    # 更新序列
                    seq_name = f"{table}_id_seq"
                    conn.execute(text(f"SELECT setval('{seq_name}', {max_id + 1}, false)"))
                    logger.info(f"序列 {seq_name} 更新为 {max_id + 1}")
            except Exception as e:
                logger.warning(f"更新序列 {table} 失败: {e}")
        
        conn.commit()


def main():
    """主函数"""
    import argparse
    from src.config.settings import DATA_DIR
    
    parser = argparse.ArgumentParser(description='PostgreSQL 数据迁移')
    parser.add_argument('--skip-backfill', action='store_true', help='跳过预计算字段回填')
    args = parser.parse_args()
    
    # 检查是否已配置 PostgreSQL
    pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    
    if not pg_url or pg_url.startswith("sqlite"):
        print("\n" + "=" * 60)
        print("PostgreSQL 迁移向导")
        print("=" * 60)
        print("\n请先运行安装脚本:")
        print("  ./scripts/setup_postgresql.sh")
        print("\n或手动配置:")
        print("1. 安装 PostgreSQL: brew install postgresql@16")
        print("2. 启动服务: brew services start postgresql@16")
        print("3. 创建数据库: createdb crypto_attention")
        print("4. 安装 pgvector: brew install pgvector")
        print("5. 设置环境变量:")
        print('   export DATABASE_URL="postgresql://localhost/crypto_attention"')
        print("\n然后重新运行此脚本。")
        return 1
    
    # SQLite 源数据库
    sqlite_url = f"sqlite:///{DATA_DIR}/crypto_attention.db"
    
    print("\n" + "=" * 60)
    print("PostgreSQL 数据迁移")
    print("=" * 60)
    print(f"\n源数据库 (SQLite): {sqlite_url}")
    print(f"目标数据库 (PostgreSQL): {pg_url[:50]}...")
    
    # Step 1: 检查 PostgreSQL 连接
    print("\n[1/6] 检查 PostgreSQL 连接...")
    if not check_postgresql_connection(pg_url):
        return 1
    
    # Step 2: 设置 pgvector
    print("\n[2/6] 设置 pgvector 扩展...")
    if not setup_pgvector(pg_url):
        print("警告: pgvector 未能安装，向量搜索功能将不可用")
        print("继续迁移其他数据...")
    
    # Step 3: 创建表结构
    print("\n[3/6] 创建 PostgreSQL 表结构...")
    create_tables_in_postgresql(pg_url)
    
    # Step 4: 迁移数据
    print("\n[4/6] 迁移数据...")
    migrate_all_data(sqlite_url, pg_url)
    
    # Step 5: 更新序列
    print("\n[5/6] 更新序列...")
    update_sequences(pg_url)
    
    # Step 6: 回填预计算字段
    if not args.skip_backfill:
        print("\n[6/6] 回填预计算字段...")
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "backfill_precomputed_features.py")],
                cwd=str(PROJECT_ROOT),
                env={**os.environ, "DATABASE_URL": pg_url},
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("  预计算字段回填完成")
            else:
                print(f"  回填警告: {result.stderr[:200] if result.stderr else '未知错误'}")
        except Exception as e:
            print(f"  回填失败: {e}")
            print("  请手动运行: python scripts/backfill_precomputed_features.py")
    else:
        print("\n[6/6] 跳过预计算字段回填 (使用 --skip-backfill)")
    
    print("\n" + "=" * 60)
    print("迁移完成!")
    print("=" * 60)
    print("\n下一步:")
    print("1. 确保 .env 文件中的 DATABASE_URL 指向 PostgreSQL")
    print("2. 重启服务: ./scripts/dev.sh")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
