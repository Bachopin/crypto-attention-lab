#!/usr/bin/env python3
"""
系统性能监控和优化建议
"""
import requests
import time
import subprocess
import json
from datetime import datetime

API_BASE = "http://localhost:8000"

def check_api_health():
    """检查API健康状态"""
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        return resp.status_code == 200
    except:
        return False

def measure_endpoint_performance():
    """测量关键端点性能"""
    endpoints = {
        "健康检查": "/health",
        "自动更新状态": "/api/auto-update/status",
        "BTC价格(最近5天)": "/api/price?symbol=BTC&granularity=1d&start=2025-11-25&end=2025-11-29",
        "BTC Attention(最近5天)": "/api/attention?symbol=BTC&start=2025-11-25&end=2025-11-29",
    }
    
    results = {}
    print("\n📊 API 性能测试")
    print("=" * 70)
    
    for name, path in endpoints.items():
        try:
            start = time.time()
            resp = requests.get(f"{API_BASE}{path}", timeout=10)
            elapsed = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                size = len(resp.content)
                results[name] = {"time": elapsed, "size": size, "status": "OK"}
                print(f"✅ {name:30} | {elapsed:7.0f}ms | {size:8,} bytes")
            else:
                results[name] = {"status": f"HTTP {resp.status_code}"}
                print(f"❌ {name:30} | HTTP {resp.status_code}")
        except Exception as e:
            results[name] = {"status": f"Error: {str(e)[:50]}"}
            print(f"❌ {name:30} | {str(e)[:50]}")
    
    print("=" * 70)
    return results

def check_background_tasks():
    """检查后台任务状态"""
    print("\n🤖 后台任务状态")
    print("=" * 70)
    
    try:
        with open('logs/api.log', 'r') as f:
            lines = f.readlines()[-100:]  # 读取最后100行
        
        # 检查最近的更新
        updater_lines = [l for l in lines if 'Updater' in l or 'Scheduler' in l]
        if updater_lines:
            print(f"✅ 最近活动: {len(updater_lines)} 条后台任务日志")
            latest = updater_lines[-1].strip()
            print(f"   最新: {latest[-100:]}")
        else:
            print("⚠️  未发现最近的后台任务活动")
            
    except Exception as e:
        print(f"❌ 无法读取日志: {e}")
    
    print("=" * 70)

def get_optimization_suggestions(perf_results):
    """根据性能结果提供优化建议"""
    print("\n💡 优化建议")
    print("=" * 70)
    
    suggestions = []
    
    # 检查响应时间
    slow_endpoints = [name for name, data in perf_results.items() 
                     if data.get('time', 0) > 1000]
    
    if slow_endpoints:
        suggestions.append("⚠️  以下端点响应时间 >1秒，考虑优化:")
        for ep in slow_endpoints:
            suggestions.append(f"   • {ep}: {perf_results[ep]['time']:.0f}ms")
        suggestions.append("   建议: 添加缓存层或优化数据库查询")
    
    # 通用优化建议
    suggestions.extend([
        "\n✅ 已完成的优化:",
        "   • feedparser 依赖已安装",
        "   • 价格更新后立即计算 Attention",
        "   • 移除重复的定时任务",
        "",
        "📋 推荐的进一步优化:",
        "   • 添加 Redis 缓存热点数据",
        "   • 数据库添加复合索引",
        "   • 前端实现虚拟滚动",
        "   • API 响应启用 gzip 压缩",
    ])
    
    for s in suggestions:
        print(s)
    
    print("=" * 70)

def main():
    print(f"\n{'='*70}")
    print(f"🔍 Crypto Attention Lab - 性能监控")
    print(f"{'='*70}")
    print(f"⏰ 检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查API是否在线
    if not check_api_health():
        print("\n❌ API 服务未响应，请先启动服务")
        print("   运行: ./scripts/start_services.sh")
        return
    
    print("✅ API 服务在线")
    
    # 性能测试
    perf_results = measure_endpoint_performance()
    
    # 后台任务
    check_background_tasks()
    
    # 优化建议
    get_optimization_suggestions(perf_results)
    
    print(f"\n{'='*70}")
    print("📋 快速操作:")
    print("   • 查看API日志: tail -f logs/api.log")
    print("   • 查看前端日志: tail -f logs/frontend.log")
    print("   • 检查状态: ./scripts/check_status.sh")
    print("   • 停止服务: ./scripts/stop_services.sh")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
