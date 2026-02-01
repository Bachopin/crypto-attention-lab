#!/usr/bin/env python3
"""
检查价格数据缺失和跳空情况

诊断工具：检查数据库中的 K 线数据完整性，找出时间跳空
不会修改任何数据，仅用于诊断
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime, timedelta, timezone
from src.data.db_storage import get_db
from src.database.models import Symbol, get_session
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_symbol_data_gaps(symbol: str, timeframe: str = '1d', days_to_check: int = 90):
    """
    检查单个代币的数据缺失情况
    
    Args:
        symbol: 代币符号，如 'BTC'
        timeframe: 时间周期，如 '1d', '4h', '1h', '15m'
        days_to_check: 检查最近多少天的数据
    """
    print(f"\n{'='*80}")
    print(f"检查 {symbol} - {timeframe} 数据完整性 (最近 {days_to_check} 天)")
    print(f"{'='*80}")
    
    db = get_db()
    
    # 加载数据
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days_to_check)
    
    df = db.get_prices(symbol, timeframe, start_time, end_time)
    
    if df.empty:
        print(f"❌ 错误: {symbol} 在 {timeframe} 时间周期没有任何数据！")
        return
    
    # 确保时间列是 datetime 类型并排序
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # 统计基本信息
    earliest = df['datetime'].min()
    latest = df['datetime'].max()
    total_records = len(df)
    
    print(f"\n📊 数据概览:")
    print(f"  - 记录总数: {total_records}")
    print(f"  - 最早时间: {earliest.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  - 最新时间: {latest.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  - 时间跨度: {(latest - earliest).days} 天")
    
    # 计算预期的时间间隔
    interval_map = {
        '1d': timedelta(days=1),
        '4h': timedelta(hours=4),
        '1h': timedelta(hours=1),
        '15m': timedelta(minutes=15)
    }
    
    expected_interval = interval_map.get(timeframe)
    if not expected_interval:
        print(f"⚠️  未知的时间周期: {timeframe}")
        return
    
    # 检查时间跳空
    print(f"\n🔍 检查时间跳空 (预期间隔: {expected_interval}):")
    
    gaps = []
    for i in range(1, len(df)):
        time_diff = df.loc[i, 'datetime'] - df.loc[i-1, 'datetime']
        
        # 如果时间差超过预期间隔的 1.5 倍，认为是跳空
        if time_diff > expected_interval * 1.5:
            missing_periods = int(time_diff / expected_interval) - 1
            gaps.append({
                'from': df.loc[i-1, 'datetime'],
                'to': df.loc[i, 'datetime'],
                'gap_duration': time_diff,
                'missing_periods': missing_periods
            })
    
    if not gaps:
        print("  ✅ 未发现显著的时间跳空！数据连续性良好。")
    else:
        print(f"  ⚠️  发现 {len(gaps)} 处时间跳空:\n")
        for idx, gap in enumerate(gaps, 1):
            print(f"  {idx}. 跳空位置:")
            print(f"     从: {gap['from'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"     到: {gap['to'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"     缺失时长: {gap['gap_duration']}")
            print(f"     缺失周期数: ~{gap['missing_periods']}")
            print()
    
    # 计算数据完整度
    expected_periods = (latest - earliest) / expected_interval
    completeness_ratio = total_records / max(1, expected_periods)
    
    print(f"📈 数据完整度:")
    print(f"  - 预期数据点: ~{int(expected_periods)}")
    print(f"  - 实际数据点: {total_records}")
    print(f"  - 完整度比例: {completeness_ratio:.2%}")
    
    if completeness_ratio < 0.95:
        print(f"  ⚠️  数据完整度低于 95%，建议重新获取历史数据")
    elif completeness_ratio < 0.98:
        print(f"  ⚙️  数据完整度尚可，但存在小缺失")
    else:
        print(f"  ✅ 数据完整度良好")
    
    return {
        'total_records': total_records,
        'gaps': gaps,
        'completeness_ratio': completeness_ratio
    }


def get_all_active_symbols():
    """获取所有活跃的代币"""
    session = get_session()
    try:
        symbols = session.query(Symbol).filter(
            Symbol.is_active == True
        ).all()
        return [s.symbol for s in symbols]
    finally:
        session.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='检查价格数据的时间跳空和缺失')
    parser.add_argument('--symbol', type=str, help='指定检查的代币符号 (如 BTC)，不指定则检查所有活跃代币')
    parser.add_argument('--timeframe', type=str, default='1d', 
                       choices=['1d', '4h', '1h', '15m'],
                       help='时间周期 (默认: 1d)')
    parser.add_argument('--days', type=int, default=90, 
                       help='检查最近多少天的数据 (默认: 90)')
    parser.add_argument('--all-timeframes', action='store_true',
                       help='检查所有时间周期')
    
    args = parser.parse_args()
    
    # 确定要检查的代币列表
    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = get_all_active_symbols()
        if not symbols:
            print("❌ 没有找到活跃的代币")
            return
        print(f"将检查 {len(symbols)} 个活跃代币: {', '.join(symbols[:10])}" + 
              (f" ... (共{len(symbols)}个)" if len(symbols) > 10 else ""))
    
    # 确定要检查的时间周期
    if args.all_timeframes:
        timeframes = ['1d', '4h', '1h', '15m']
    else:
        timeframes = [args.timeframe]
    
    # 汇总结果
    results = {}
    issues_found = []
    
    for symbol in symbols:
        results[symbol] = {}
        for timeframe in timeframes:
            try:
                result = check_symbol_data_gaps(symbol, timeframe, args.days)
                results[symbol][timeframe] = result
                
                if result and (len(result['gaps']) > 0 or result['completeness_ratio'] < 0.95):
                    issues_found.append({
                        'symbol': symbol,
                        'timeframe': timeframe,
                        'gaps': len(result['gaps']),
                        'completeness': result['completeness_ratio']
                    })
            except Exception as e:
                print(f"❌ 检查 {symbol} {timeframe} 时出错: {e}")
    
    # 打印汇总报告
    print(f"\n{'='*80}")
    print("📋 检查汇总报告")
    print(f"{'='*80}")
    
    if not issues_found:
        print("✅ 所有检查的代币和时间周期数据完整性良好！")
    else:
        print(f"⚠️  发现 {len(issues_found)} 个数据问题:\n")
        for issue in issues_found:
            print(f"  - {issue['symbol']} ({issue['timeframe']}): "
                  f"{issue['gaps']} 处跳空, 完整度 {issue['completeness']:.2%}")
        
        print(f"\n💡 建议:")
        print(f"  1. 运行 './scripts/refetch_historical_prices.py' 重新获取历史数据")
        print(f"  2. 或通过 API 手动触发刷新: POST /api/refresh-symbol?symbol=XXX&check_completeness=true")


if __name__ == '__main__':
    main()
