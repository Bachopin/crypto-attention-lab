#!/usr/bin/env python3
"""
API 性能测试脚本
测试关键 API 端点的响应时间
"""

import time
import requests
import statistics
from typing import List, Dict, Any

API_BASE_URL = "http://localhost:8000"

def measure_endpoint(endpoint: str, params: Dict[str, Any] = None, n_runs: int = 5) -> Dict[str, float]:
    """测量端点的响应时间"""
    times: List[float] = []
    
    for _ in range(n_runs):
        start = time.time()
        try:
            response = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=30)
            response.raise_for_status()
            elapsed = time.time() - start
            times.append(elapsed)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return {"error": str(e)}
    
    return {
        "min": min(times),
        "max": max(times),
        "avg": statistics.mean(times),
        "median": statistics.median(times),
        "runs": n_runs
    }

def main():
    print("🚀 Crypto Attention Lab - API Performance Test\n")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        ("Health Check", "/health", {}),
        ("Symbols List", "/api/symbols", {}),
        ("Price Data (BTC, 1D)", "/api/price", {"symbol": "BTCUSDT", "timeframe": "1d"}),
        ("Price Data (BTC, 15M, 96 candles)", "/api/price", {"symbol": "BTCUSDT", "timeframe": "15m"}),
        ("Attention Data (BTC)", "/api/attention", {"symbol": "BTC", "granularity": "1d"}),
        ("News Data (ALL, 100 items)", "/api/news", {"symbol": "ALL", "limit": 100}),
        ("News Data (BTC)", "/api/news", {"symbol": "BTC"}),
        ("Attention Events (BTC)", "/api/attention-events", {"symbol": "BTC", "lookback_days": 30}),
        ("Auto-Update Status", "/api/auto-update/status", {}),
    ]
    
    results = []
    
    for name, endpoint, params in test_cases:
        print(f"\n📊 Testing: {name}")
        print(f"   Endpoint: {endpoint}")
        if params:
            print(f"   Params: {params}")
        
        result = measure_endpoint(endpoint, params, n_runs=3)
        
        if "error" in result:
            print(f"   ❌ Failed: {result['error']}")
        else:
            print(f"   ✅ Min: {result['min']*1000:.1f}ms | Avg: {result['avg']*1000:.1f}ms | Max: {result['max']*1000:.1f}ms")
            results.append({
                "name": name,
                "endpoint": endpoint,
                **result
            })
    
    print("\n" + "=" * 60)
    print("\n📈 Performance Summary:")
    print("-" * 60)
    
    # 排序结果
    results.sort(key=lambda x: x['avg'])
    
    for i, r in enumerate(results, 1):
        status = "🟢" if r['avg'] < 0.5 else "🟡" if r['avg'] < 2.0 else "🔴"
        print(f"{status} {i}. {r['name']:<40} {r['avg']*1000:>6.1f}ms")
    
    # 性能建议
    print("\n" + "=" * 60)
    print("\n💡 Performance Recommendations:")
    slow_endpoints = [r for r in results if r['avg'] > 2.0]
    
    if slow_endpoints:
        print("\n⚠️  Slow endpoints (>2s):")
        for r in slow_endpoints:
            print(f"   - {r['name']}: {r['avg']*1000:.1f}ms")
            print(f"     → Consider adding caching or optimization")
    else:
        print("\n✅ All endpoints are performing well (<2s)")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
