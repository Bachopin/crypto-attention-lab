#!/usr/bin/env python3
"""
迁移脚本：为 symbols 表添加自动更新相关列
"""
import sqlite3
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.settings import DATA_DIR


def migrate_database():
    """添加 auto_update_price 和 last_price_update 列"""
    db_path = DATA_DIR / "crypto_attention.db"
    print(f"Migrating database: {db_path}")
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # 检查列是否已存在
        cursor.execute("PRAGMA table_info(symbols)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 添加 auto_update_price 列
        if 'auto_update_price' not in columns:
            print("Adding column: auto_update_price")
            cursor.execute("""
                ALTER TABLE symbols 
                ADD COLUMN auto_update_price BOOLEAN DEFAULT 0
            """)
            conn.commit()
            print("✓ Column auto_update_price added")
        else:
            print("✓ Column auto_update_price already exists")
        
        # 添加 last_price_update 列
        if 'last_price_update' not in columns:
            print("Adding column: last_price_update")
            cursor.execute("""
                ALTER TABLE symbols 
                ADD COLUMN last_price_update DATETIME
            """)
            conn.commit()
            print("✓ Column last_price_update added")
        else:
            print("✓ Column last_price_update already exists")
        
        print("\n✅ Migration completed successfully")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    migrate_database()
