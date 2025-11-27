import os
import sys
from typing import Any

# Ensure project root in sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # type: ignore
from src.api.main import app


client = TestClient(app)


def test_health() -> None:
    resp = client.get('/health')
    assert resp.status_code == 200
    data = resp.json()
    assert data.get('status') == 'healthy'


def test_attention_events_endpoint() -> None:
    params = {"symbol": "ZEC", "lookback_days": 30, "min_quantile": 0.8}
    resp = client.get('/api/attention-events', params=params)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # If non-empty, validate schema keys
    if data:
        item = data[0]
        assert set(['datetime', 'event_type', 'intensity', 'summary']).issubset(item.keys())


def test_backtest_basic_attention_endpoint() -> None:
    payload = {
        "symbol": "ZECUSDT",
        "lookback_days": 30,
        "attention_quantile": 0.8,
        "max_daily_return": 0.05,
        "holding_days": 3,
    }
    resp = client.post('/api/backtest/basic-attention', json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert set(['summary', 'trades', 'equity_curve']).issubset(data.keys())
    assert isinstance(data['trades'], list)
    assert isinstance(data['equity_curve'], list)
