#!/usr/bin/env python3
"""
数据库迁移脚本：添加预计算相关表和字段

添加内容：
1. Symbol 表新增字段：
   - event_performance_cache (Text): 事件表现统计缓存 (JSON)
   - event_performance_updated_at (DateTime): 缓存更新时间

2. 新增 state_snapshots 表：
   - id: 主键
   - symbol_id: 外键关联 symbols
   - datetime: 快照时间
   - timeframe: 时间粒度 ('1d' 或 '4h')
   - window_days: 窗口天数 (固定 30)
   - features: JSON 特征向量
   - raw_stats: JSON 原始统计
   - created_at: 创建时间

使用方法：
    python scripts/migrate_add_precomputation_tables.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from src.database.models import get_engine, Base, StateSnapshot, Symbol


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """检查列是否存在"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def check_table_exists(engine, table_name: str) -> bool:
    """检查表是否存在"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate():
    """执行迁移"""
    engine = get_engine()
    
    print("=" * 60)
    print("数据库迁移：添加预计算相关表和字段")
    print("=" * 60)
    
    with engine.connect() as conn:
        # 1. 添加 Symbol 表的新字段
        print("\n1. 检查 symbols 表字段...")
        
        if not check_column_exists(engine, 'symbols', 'event_performance_cache'):
            print("   添加 event_performance_cache 字段...")
            conn.execute(text(
                "ALTER TABLE symbols ADD COLUMN event_performance_cache TEXT"
            ))
            print("   ✓ event_performance_cache 已添加")
        else:
            print("   ✓ event_performance_cache 已存在")
        
        if not check_column_exists(engine, 'symbols', 'event_performance_updated_at'):
            print("   添加 event_performance_updated_at 字段...")
            conn.execute(text(
                "ALTER TABLE symbols ADD COLUMN event_performance_updated_at DATETIME"
            ))
            print("   ✓ event_performance_updated_at 已添加")
        else:
            print("   ✓ event_performance_updated_at 已存在")
        
        conn.commit()
        
        # 2. 创建 state_snapshots 表
        print("\n2. 检查 state_snapshots 表...")
        
        if not check_table_exists(engine, 'state_snapshots'):
            print("   创建 state_snapshots 表...")
            # 使用 SQLAlchemy 的 create_all 只创建不存在的表
            StateSnapshot.__table__.create(engine, checkfirst=True)
            print("   ✓ state_snapshots 表已创建")
        else:
            print("   ✓ state_snapshots 表已存在")
    
    print("\n" + "=" * 60)
    print("迁移完成！")
    print("=" * 60)
    
    # 验证
    print("\n验证结果：")
    inspector = inspect(engine)
    
    # 验证 symbols 表字段
    symbols_columns = [col['name'] for col in inspector.get_columns('symbols')]
    print(f"  symbols 表字段: {', '.join(symbols_columns)}")
    
    # 验证 state_snapshots 表
    if check_table_exists(engine, 'state_snapshots'):
        ss_columns = [col['name'] for col in inspector.get_columns('state_snapshots')]
        print(f"  state_snapshots 表字段: {', '.join(ss_columns)}")
    
    print("\n提示：请重启 API 服务以应用更改。")


if __name__ == "__main__":
    migrate()
