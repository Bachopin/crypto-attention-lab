"""
API 测试 - 优化版

使用共享 fixtures 避免重复创建 TestClient
"""
import pytest


class TestHealthAndBasicAPIs:
    """健康检查和基础 API 测试"""

    def test_health(self, client) -> None:
        resp = client.get('/health')
        assert resp.status_code == 200
        data = resp.json()
        assert data.get('status') == 'healthy'

    def test_symbols_endpoint(self, client) -> None:
        resp = client.get('/api/symbols')
        assert resp.status_code == 200
        data = resp.json()
        assert 'symbols' in data
        assert isinstance(data['symbols'], list)


class TestAttentionAPIs:
    """注意力相关 API 测试"""

    def test_attention_events_endpoint(self, client) -> None:
        params = {"symbol": "ZEC", "lookback_days": 30, "min_quantile": 0.8}
        resp = client.get('/api/attention-events', params=params)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # If non-empty, validate schema keys
        if data:
            item = data[0]
            assert set(['datetime', 'event_type', 'intensity', 'summary']).issubset(item.keys())

    def test_attention_with_extended_features(self, client) -> None:
        """测试注意力 API 返回扩展特征"""
        response = client.get("/api/attention", params={"symbol": "ZEC"})
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            att = data[0]
            assert "attention_score" in att
            assert "news_count" in att


class TestBacktestAPIs:
    """回测 API 测试"""

    @pytest.fixture
    def backtest_payload(self):
        return {
            "symbol": "ZECUSDT",
            "lookback_days": 30,
            "attention_quantile": 0.8,
            "max_daily_return": 0.05,
            "holding_days": 3,
        }

    def test_backtest_basic_attention_endpoint(self, client, backtest_payload) -> None:
        resp = client.post('/api/backtest/basic-attention', json=backtest_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert set(['summary', 'trades', 'equity_curve']).issubset(data.keys())
        assert isinstance(data['trades'], list)
        assert isinstance(data['equity_curve'], list)

    def test_backtest_summary_structure(self, client, backtest_payload) -> None:
        """测试回测 summary 结构"""
        resp = client.post('/api/backtest/basic-attention', json=backtest_payload)
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        
        expected_keys = ["total_trades", "win_rate", "avg_return", "cumulative_return", "max_drawdown"]
        for key in expected_keys:
            assert key in summary, f"Missing key: {key}"


class TestNewsAPIs:
    """新闻 API 测试"""

    def test_news_with_features(self, client) -> None:
        """测试新闻 API 返回扩展字段"""
        response = client.get("/api/news", params={"symbol": "ZEC"})
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            news = data[0]
            # 检查必需字段
            assert "title" in news or "source_weight" in news
