"""
测试注意力事件和回测 API
"""
import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_check():
    """测试健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_attention_events_api():
    """测试注意力事件 API"""
    response = client.get("/api/attention-events", params={
        "symbol": "ZEC",
        "lookback_days": 30,
        "min_quantile": 0.8
    })
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    # 如果有事件，检查结构
    if len(data) > 0:
        event = data[0]
        assert "datetime" in event
        assert "event_type" in event
        assert "intensity" in event
        assert "summary" in event


def test_backtest_api():
    """测试回测 API"""
    response = client.post("/api/backtest/basic-attention", json={
        "symbol": "ZECUSDT",
        "lookback_days": 30,
        "attention_quantile": 0.8,
        "max_daily_return": 0.05,
        "holding_days": 3
    })
    assert response.status_code == 200
    data = response.json()
    
    # 检查返回结构
    assert "summary" in data
    assert "trades" in data
    assert "equity_curve" in data
    
    # 检查 summary 结构
    summary = data["summary"]
    assert "total_trades" in summary
    assert "win_rate" in summary
    assert "avg_return" in summary
    assert "cumulative_return" in summary
    assert "max_drawdown" in summary


def test_news_with_features():
    """测试新闻 API 返回扩展字段"""
    response = client.get("/api/news", params={"symbol": "ZEC"})
    assert response.status_code == 200
    data = response.json()
    
    # 如果有新闻，检查扩展字段
    if len(data) > 0:
        news = data[0]
        assert "source_weight" in news
        assert "sentiment_score" in news
        assert "tags" in news
        assert "relevance" in news


def test_attention_with_extended_features():
    """测试注意力 API 返回扩展特征"""
    response = client.get("/api/attention", params={"symbol": "ZEC"})
    assert response.status_code == 200
    data = response.json()
    
    # 如果有数据，检查扩展字段
    if len(data) > 0:
        att = data[0]
        assert "attention_score" in att
        assert "news_count" in att
        assert "weighted_attention" in att
        assert "bullish_attention" in att
        assert "bearish_attention" in att
        assert "event_intensity" in att


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
