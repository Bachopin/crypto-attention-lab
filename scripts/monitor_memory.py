#!/usr/bin/env python3
"""
内存监控脚本
用于检测后端进程的内存使用情况和可能的内存泄露
"""

import psutil
import time
import argparse
from datetime import datetime


def find_process_by_pattern(pattern: str):
    """根据命令行模式查找进程"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if pattern in cmdline:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def format_bytes(bytes_val):
    """格式化字节数"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} TB"


def monitor_memory(interval=5, duration=None, pattern="uvicorn"):
    """
    监控进程内存
    
    Args:
        interval: 检查间隔（秒）
        duration: 监控持续时间（秒），None 表示持续监控
        pattern: 进程命令行匹配模式
    """
    print(f"🔍 正在查找进程（pattern: {pattern}）...")
    proc = find_process_by_pattern(pattern)
    
    if not proc:
        print(f"❌ 未找到匹配的进程")
        return
    
    print(f"✅ 找到进程: PID={proc.pid}, Name={proc.name()}")
    print(f"📊 开始监控（间隔: {interval}s）\n")
    print(f"{'Time':<20} {'RSS':<15} {'VMS':<15} {'CPU%':<10} {'Threads':<10}")
    print("-" * 70)
    
    start_time = time.time()
    baseline_rss = None
    
    try:
        while True:
            try:
                # 获取内存信息
                mem_info = proc.memory_info()
                cpu_percent = proc.cpu_percent(interval=0.1)
                num_threads = proc.num_threads()
                
                rss = mem_info.rss  # 实际物理内存
                vms = mem_info.vms  # 虚拟内存
                
                if baseline_rss is None:
                    baseline_rss = rss
                
                # 计算内存增长
                growth = rss - baseline_rss
                growth_pct = (growth / baseline_rss * 100) if baseline_rss > 0 else 0
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(
                    f"{timestamp:<20} "
                    f"{format_bytes(rss):<15} "
                    f"{format_bytes(vms):<15} "
                    f"{cpu_percent:<10.1f} "
                    f"{num_threads:<10}"
                )
                
                # 内存泄露警告
                if growth_pct > 50:
                    print(f"⚠️  内存增长 {growth_pct:.1f}% (+{format_bytes(growth)})")
                
                # CPU 高占用警告
                if cpu_percent > 80:
                    print(f"⚠️  CPU 高占用: {cpu_percent:.1f}%")
                
                # 线程泄露警告
                if num_threads > 50:
                    print(f"⚠️  线程数过多: {num_threads}")
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print(f"❌ 进程已退出或无访问权限")
                break
            
            time.sleep(interval)
            
            # 检查持续时间
            if duration and (time.time() - start_time) >= duration:
                break
                
    except KeyboardInterrupt:
        print("\n\n✋ 监控已停止")
        
        # 显示总结
        if baseline_rss:
            final_mem = proc.memory_info().rss
            total_growth = final_mem - baseline_rss
            total_growth_pct = (total_growth / baseline_rss * 100)
            
            print("\n" + "=" * 70)
            print("📊 监控总结")
            print("=" * 70)
            print(f"初始内存: {format_bytes(baseline_rss)}")
            print(f"最终内存: {format_bytes(final_mem)}")
            print(f"内存增长: {format_bytes(total_growth)} ({total_growth_pct:+.1f}%)")
            print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="监控进程内存使用")
    parser.add_argument("-i", "--interval", type=int, default=5, help="检查间隔（秒）")
    parser.add_argument("-d", "--duration", type=int, help="监控持续时间（秒）")
    parser.add_argument("-p", "--pattern", default="uvicorn", help="进程命令行匹配模式")
    
    args = parser.parse_args()
    
    monitor_memory(
        interval=args.interval,
        duration=args.duration,
        pattern=args.pattern
    )
