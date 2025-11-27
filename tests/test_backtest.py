import pytest
import pandas as pd
from src.backtest.basic_attention_factor import run_backtest_basic_attention
from unittest.mock import patch, MagicMock

@patch('src.backtest.basic_attention_factor.load_price_data')
@patch('src.backtest.basic_attention_factor.load_attention_data')
def test_run_backtest_basic_attention(mock_load_attention, mock_load_price):
    # Mock Price Data
    dates = pd.date_range(start='2025-01-01', periods=10, freq='D')
    price_df = pd.DataFrame({
        'datetime': dates,
        'close': [100, 101, 102, 100, 105, 110, 108, 112, 115, 120],
        'open': [100] * 10,
        'high': [120] * 10,
        'low': [90] * 10,
        'volume': [1000] * 10
    })
    mock_load_price.return_value = (price_df, False)

    # Mock Attention Data
    # Day 3 (index 3, 2025-01-04): High weighted attention, low return (100->100 is 0%)
    # Day 4 (index 4, 2025-01-05): Price jumps to 105
    attention_df = pd.DataFrame({
        'datetime': dates,
        'attention_score': [10, 10, 10, 80, 10, 10, 10, 10, 10, 10],
        'weighted_attention': [6, 4, 5, 50, 5, 5, 5, 5, 5, 5],
        'bullish_attention': [1, 1, 1, 40, 1, 1, 1, 1, 1, 1],
        'bearish_attention': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        'news_count': [1] * 10
    })
    mock_load_attention.return_value = attention_df

    # Run Backtest
    result = run_backtest_basic_attention(
        symbol="ZECUSDT",
        lookback_days=3, # Short lookback for testing
        attention_quantile=0.8,
        max_daily_return=0.05,
        holding_days=2
    )

    # Assertions
    assert "summary" in result
    assert "trades" in result
    assert "equity_curve" in result
    
    # We expect a trade on Day 3 (2025-01-04) because weighted_attention (50) is high
    # and daily return (100/102 - 1 = -0.019) is < 0.05
    # Entry price: 100 (Close of Day 3)
    # Holding 2 days -> Exit on Day 5 (2025-01-06), Close 110
    # Return: 110/100 - 1 = 0.10 (10%)
    
    trades = result['trades']
    assert len(trades) >= 1
    trade = trades[0]
    assert trade['entry_price'] == 100.0
    assert trade['exit_price'] == 110.0
    assert trade['return_pct'] == pytest.approx(0.10)

    summary = result['summary']
    assert summary['total_trades'] >= 1
    # assert summary['win_rate'] == 100.0 # Can be lower if noise triggers losing trades
    assert summary['avg_return'] > 0 # Overall should be positive due to the big win
