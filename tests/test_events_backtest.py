"""
测试注意力事件和回测 API - 优化版

使用共享 fixtures，避免重复创建 TestClient
"""
import pytest


class TestHealthCheck:
    """健康检查测试"""

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestAttentionEventsAPI:
    """注意力事件 API 测试"""

    def test_attention_events_api(self, client):
        """测试注意力事件 API"""
        response = client.get("/api/attention-events", params={
            "symbol": "ZEC",
            "lookback_days": 30,
            "min_quantile": 0.8
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            event = data[0]
            assert "datetime" in event
            assert "event_type" in event
            assert "intensity" in event
            assert "summary" in event


class TestBacktestAPI:
    """回测 API 测试"""

    @pytest.fixture
    def backtest_params(self):
        return {
            "symbol": "ZECUSDT",
            "lookback_days": 30,
            "attention_quantile": 0.8,
            "max_daily_return": 0.05,
            "holding_days": 3
        }

    def test_backtest_api(self, client, backtest_params):
        """测试回测 API"""
        response = client.post("/api/backtest/basic-attention", json=backtest_params)
        assert response.status_code == 200
        data = response.json()
        
        assert "summary" in data
        assert "trades" in data
        assert "equity_curve" in data
        
        summary = data["summary"]
        assert "total_trades" in summary
        assert "win_rate" in summary
        assert "avg_return" in summary
        assert "cumulative_return" in summary
        assert "max_drawdown" in summary


class TestNewsAPI:
    """新闻 API 测试"""

    def test_news_with_features(self, client):
        """测试新闻 API 返回扩展字段"""
        response = client.get("/api/news", params={"symbol": "ZEC"})
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            news = data[0]
            # 至少包含基础字段
            assert "title" in news or "source" in news


class TestAttentionAPI:
    """注意力 API 测试"""

    def test_attention_with_extended_features(self, client):
        """测试注意力 API 返回扩展特征"""
        response = client.get("/api/attention", params={"symbol": "ZEC"})
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            att = data[0]
            assert "attention_score" in att
            assert "news_count" in att
