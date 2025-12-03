#!/usr/bin/env python3
"""
修复时区导致的重复数据问题

问题描述：
- 数据库中 attention_features 表每天有两行数据
- 一行是 08:00:00+08:00（= UTC 00:00:00，正确）
- 一行是 00:00:00+08:00（= UTC 16:00:00 前一天，错误/空数据）

解决方案：
1. 删除所有 00:00:00+08:00 的记录（这些是时区处理错误产生的）
2. 可选：同时修复 prices 表的时间戳

使用方法:
    python scripts/fix_timezone_duplicates.py --dry-run  # 预览，不执行
    python scripts/fix_timezone_duplicates.py            # 实际执行
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging
from sqlalchemy import create_engine, text
from src.config.settings import DATABASE_URL

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_duplicates(engine):
    """分析重复数据的情况"""
    with engine.connect() as conn:
        # 统计不同时间格式的数据
        result = conn.execute(text('''
            SELECT 
                datetime::time as time_part,
                COUNT(*) as cnt,
                SUM(CASE WHEN news_count = 0 THEN 1 ELSE 0 END) as empty_cnt,
                SUM(CASE WHEN news_count > 0 THEN 1 ELSE 0 END) as with_data_cnt
            FROM attention_features
            GROUP BY datetime::time
            ORDER BY cnt DESC
        '''))
        
        print("\n" + "=" * 70)
        print("attention_features 时间分布分析")
        print("=" * 70)
        print(f"{'时间部分':<20} {'总数':<10} {'空数据':<10} {'有数据':<10}")
        print("-" * 70)
        
        bad_time = None
        bad_count = 0
        
        for r in result.fetchall():
            time_part = str(r[0])
            print(f"{time_part:<20} {r[1]:<10} {r[2]:<10} {r[3]:<10}")
            
            # 00:00:00 本地时间的记录大多是空的（错误数据）
            if time_part == '00:00:00' and r[2] > r[3]:
                bad_time = time_part
                bad_count = r[1]
        
        print("=" * 70)
        
        if bad_time:
            print(f"\n⚠️  发现问题：{bad_count} 条 '{bad_time}' 时间的记录大多为空")
            print("   这些是时区处理错误导致的重复数据")
        
        # 检查 prices 表
        result2 = conn.execute(text('''
            SELECT 
                datetime::time as time_part,
                COUNT(*) as cnt
            FROM prices
            WHERE timeframe = '1d'
            GROUP BY datetime::time
            ORDER BY cnt DESC
        '''))
        
        print("\n" + "=" * 70)
        print("prices (1d) 时间分布分析")
        print("=" * 70)
        for r in result2.fetchall():
            print(f"  {r[0]}: {r[1]} 条")
        print("=" * 70)
        
        return bad_count


def fix_attention_features(engine, dry_run=True):
    """删除错误的 attention_features 记录"""
    
    with engine.connect() as conn:
        # 先统计要删除的记录
        result = conn.execute(text('''
            SELECT COUNT(*) 
            FROM attention_features 
            WHERE datetime::time = '00:00:00'
        '''))
        count = result.fetchone()[0]
        
        if count == 0:
            print("\n✅ 没有需要删除的 attention_features 记录")
            return 0
        
        print(f"\n将删除 {count} 条 '00:00:00+08:00' 的 attention_features 记录")
        
        if dry_run:
            print("   [DRY RUN] 不执行实际删除")
            return count
        
        # 执行删除
        conn.execute(text('''
            DELETE FROM attention_features 
            WHERE datetime::time = '00:00:00'
        '''))
        conn.commit()
        
        print(f"   ✅ 已删除 {count} 条记录")
        return count


def fix_prices(engine, dry_run=True):
    """
    修复 prices 表的时间戳
    
    将 00:00:00+08:00 转换为正确的 08:00:00+08:00（即 UTC 00:00:00）
    
    注意：这里我们把本地午夜的时间戳向后移动 8 小时，使其变成 UTC 午夜
    """
    
    with engine.connect() as conn:
        # 统计需要修复的记录
        result = conn.execute(text('''
            SELECT COUNT(*) 
            FROM prices 
            WHERE timeframe = '1d' AND datetime::time = '00:00:00'
        '''))
        count = result.fetchone()[0]
        
        if count == 0:
            print("\n✅ 没有需要修复的 prices 记录")
            return 0
        
        print(f"\n将修复 {count} 条 '00:00:00+08:00' 的 prices 记录")
        print("   转换：00:00:00+08:00 → 08:00:00+08:00 (即 UTC 00:00:00)")
        
        if dry_run:
            print("   [DRY RUN] 不执行实际修复")
            # 显示一些示例
            result2 = conn.execute(text('''
                SELECT datetime, datetime + interval '8 hours' as fixed
                FROM prices 
                WHERE timeframe = '1d' AND datetime::time = '00:00:00'
                ORDER BY datetime DESC
                LIMIT 5
            '''))
            print("\n   示例转换：")
            for r in result2.fetchall():
                print(f"     {r[0]} → {r[1]}")
            return count
        
        # 执行更新
        conn.execute(text('''
            UPDATE prices 
            SET datetime = datetime + interval '8 hours'
            WHERE timeframe = '1d' AND datetime::time = '00:00:00'
        '''))
        conn.commit()
        
        print(f"   ✅ 已修复 {count} 条记录")
        return count


def main():
    parser = argparse.ArgumentParser(description='修复时区导致的重复数据问题')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='预览模式，不执行实际修改'
    )
    parser.add_argument(
        '--fix-prices',
        action='store_true',
        help='同时修复 prices 表的时间戳'
    )
    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='仅分析，不做任何修复'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("时区重复数据修复工具")
    print("=" * 70)
    
    if args.dry_run:
        print("📋 模式: DRY RUN（预览，不执行）")
    elif args.analyze_only:
        print("📋 模式: ANALYZE ONLY（仅分析）")
    else:
        print("🔧 模式: EXECUTE（将执行修改！）")
    
    engine = create_engine(DATABASE_URL)
    
    # 分析
    bad_count = analyze_duplicates(engine)
    
    if args.analyze_only:
        return 0
    
    if bad_count == 0:
        print("\n✅ 未发现需要修复的数据")
        return 0
    
    # 确认执行
    if not args.dry_run:
        confirm = input("\n确认执行修复？(yes/no): ")
        if confirm.lower() != 'yes':
            print("已取消")
            return 1
    
    # 修复 attention_features
    fix_attention_features(engine, dry_run=args.dry_run)
    
    # 可选：修复 prices
    if args.fix_prices:
        fix_prices(engine, dry_run=args.dry_run)
    
    print("\n" + "=" * 70)
    if args.dry_run:
        print("DRY RUN 完成。使用不带 --dry-run 的命令来执行实际修复。")
    else:
        print("✅ 修复完成！")
    print("=" * 70 + "\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
