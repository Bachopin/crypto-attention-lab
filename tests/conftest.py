"""
Pytest 配置和通用 fixtures

优化要点：
1. 使用 session/module 级别的 fixtures 减少重复初始化
2. 正确清理 TestClient 避免内存泄漏
3. 复用 mock 数据
"""
import os
import sys
import gc
from typing import Generator
import pytest
import pandas as pd

# 确保项目根目录在 sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def app():
    """Session 级别的 FastAPI app，整个测试会话只创建一次"""
    from src.api.main import app as fastapi_app
    yield fastapi_app


@pytest.fixture(scope="module")
def client(app):
    """
    Module 级别的 TestClient
    
    每个测试模块共享一个 client，减少创建/销毁开销
    使用 context manager 确保正确清理连接
    """
    from fastapi.testclient import TestClient
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    # 显式触发垃圾回收
    gc.collect()


@pytest.fixture(scope="session")
def mock_price_data() -> pd.DataFrame:
    """复用的模拟价格数据"""
    dates = pd.date_range(start='2025-01-01', periods=10, freq='D')
    return pd.DataFrame({
        'datetime': dates,
        'close': [100, 101, 102, 100, 105, 110, 108, 112, 115, 120],
        'open': [100] * 10,
        'high': [120] * 10,
        'low': [90] * 10,
        'volume': [1000] * 10
    })


@pytest.fixture(scope="session")
def mock_attention_data() -> pd.DataFrame:
    """复用的模拟注意力数据"""
    dates = pd.date_range(start='2025-01-01', periods=10, freq='D')
    return pd.DataFrame({
        'datetime': dates,
        'attention_score': [10, 10, 10, 80, 10, 10, 10, 10, 10, 10],
        'weighted_attention': [6, 4, 5, 50, 5, 5, 5, 5, 5, 5],
        'bullish_attention': [1, 1, 1, 40, 1, 1, 1, 1, 1, 1],
        'bearish_attention': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        'news_count': [1] * 10
    })


@pytest.fixture(autouse=True)
def cleanup():
    """每个测试后清理"""
    yield
    gc.collect()


def pytest_configure(config):
    """Pytest 配置钩子"""
    # 设置测试环境变量
    os.environ.setdefault('TESTING', '1')


def pytest_collection_modifyitems(config, items):
    """修改测试收集，自动添加标记"""
    for item in items:
        # 根据文件名自动添加标记
        if "test_api" in item.nodeid or "test_events" in item.nodeid:
            item.add_marker(pytest.mark.api)
        if "test_backtest" in item.nodeid:
            item.add_marker(pytest.mark.unit)
