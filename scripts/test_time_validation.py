#!/usr/bin/env python3
"""
测试时间戳验证功能
验证前后端对无效时间戳的处理
"""

import requests
from datetime import datetime, timedelta

API_BASE_URL = "http://localhost:8000"

def test_endpoint(name, endpoint, params):
    """测试单个端点的时间验证"""
    print(f"\n🧪 Testing {name}")
    print(f"   Params: {params}")
    
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params, timeout=10)
        
        if response.status_code == 200:
            print(f"   ✅ Success: {response.status_code}")
            return True
        elif response.status_code == 400:
            error = response.json()
            print(f"   ✅ Correctly rejected: {error.get('detail', 'Unknown error')}")
            return True
        else:
            print(f"   ⚠️  Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("=" * 70)
    print("🔍 Time Validation Test Suite")
    print("=" * 70)
    
    # 测试用例
    test_cases = [
        # 正常的时间范围
        ("Valid recent time", "/api/news", {
            "symbol": "BTC",
            "start": (datetime.now() - timedelta(days=7)).isoformat(),
            "limit": 10
        }),
        
        # 无效的时间 - 公元2年
        ("Invalid ancient time (year 2)", "/api/news", {
            "symbol": "BTC",
            "start": "0002-11-21T00:00:00Z",
            "limit": 10
        }),
        
        # 无效的时间 - 早于2009年
        ("Invalid time before 2009", "/api/news", {
            "symbol": "BTC",
            "start": "2008-01-01T00:00:00Z",
            "limit": 10
        }),
        
        # before 参数测试 - 正常
        ("Valid before parameter", "/api/news", {
            "symbol": "BTC",
            "before": (datetime.now() - timedelta(days=1)).isoformat(),
            "limit": 10
        }),
        
        # before 参数测试 - 无效
        ("Invalid before parameter", "/api/news", {
            "symbol": "BTC",
            "before": "0002-11-21T00:00:00Z",
            "limit": 10
        }),
        
        # 价格数据端点测试
        ("Price API - valid time", "/api/price", {
            "symbol": "BTCUSDT",
            "timeframe": "1d",
            "start": (datetime.now() - timedelta(days=30)).isoformat()
        }),
        
        ("Price API - invalid ancient time", "/api/price", {
            "symbol": "BTCUSDT",
            "timeframe": "1d",
            "start": "0002-11-21T00:00:00Z"
        }),
        
        # Attention 数据端点测试
        ("Attention API - valid time", "/api/attention", {
            "symbol": "BTC",
            "start": (datetime.now() - timedelta(days=30)).isoformat()
        }),
        
        ("Attention API - invalid time", "/api/attention", {
            "symbol": "BTC",
            "start": "2007-01-01T00:00:00Z"
        }),
        
        # 新闻计数端点测试
        ("News count - valid", "/api/news/count", {
            "symbol": "BTC",
            "start": (datetime.now() - timedelta(days=7)).isoformat()
        }),
        
        ("News count - invalid", "/api/news/count", {
            "symbol": "BTC",
            "start": "0002-11-21T00:00:00Z"
        }),
    ]
    
    results = []
    for name, endpoint, params in test_cases:
        result = test_endpoint(name, endpoint, params)
        results.append((name, result))
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("📊 Test Results Summary")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n📈 Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
