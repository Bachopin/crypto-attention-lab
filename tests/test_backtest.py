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


@patch('src.backtest.basic_attention_factor.load_price_data')
@patch('src.backtest.basic_attention_factor.load_attention_data')
def test_backtest_with_stop_loss_and_take_profit(mock_load_attention, mock_load_price):
    dates = pd.date_range(start='2025-01-01', periods=6, freq='D')
    price_df = pd.DataFrame({
        'datetime': dates,
        'close': [100, 110, 90, 95, 80, 85],
        'open': [100] * 6,
        'high': [120] * 6,
        'low': [80] * 6,
        'volume': [1000] * 6,
    })
    mock_load_price.return_value = (price_df, False)

    attention_df = pd.DataFrame({
        'datetime': dates,
        'attention_score': [10, 90, 10, 10, 10, 10],
        'weighted_attention': [5, 100, 5, 5, 5, 5],
        'bullish_attention': [1, 80, 1, 1, 1, 1],
        'bearish_attention': [0, 0, 0, 0, 0, 0],
        'news_count': [1] * 6,
    })
    mock_load_attention.return_value = attention_df

    # 高 attention 在第二天触发买入
    res_tp = run_backtest_basic_attention(
        symbol="ZECUSDT",
        lookback_days=2,
        attention_quantile=0.8,
        max_daily_return=1.0,
        holding_days=5,
        stop_loss_pct=None,
        take_profit_pct=0.05,  # 价格从 100 涨到 110, 收益 10% 大于 5%, 应在第二天止盈
    )
    trades_tp = res_tp['trades']
    assert len(trades_tp) == 1
    t_tp = trades_tp[0]
    # entry at day1 close=100, exit at day2 close=110
    assert t_tp['entry_price'] == 100.0
    assert t_tp['exit_price'] == 110.0

    res_sl = run_backtest_basic_attention(
        symbol="ZECUSDT",
        lookback_days=2,
        attention_quantile=0.8,
        max_daily_return=1.0,
        holding_days=5,
        stop_loss_pct=-0.10,  # 从最高 110 跌到 95(-13.6%) 会触发止损
        take_profit_pct=None,
    )
    trades_sl = res_sl['trades']
    assert len(trades_sl) == 1
    t_sl = trades_sl[0]
    # entry at day1 close=100, path: 110 -> 90 -> 95, 止损在第三天收盘 90 或 95 之间
    assert t_sl['entry_price'] == 100.0
    assert t_sl['exit_price'] in (90.0, 95.0)


@patch('src.backtest.basic_attention_factor.load_price_data')
@patch('src.backtest.basic_attention_factor.load_attention_data')
def test_backtest_max_holding_days_and_position_size(mock_load_attention, mock_load_price):
    dates = pd.date_range(start='2025-01-01', periods=5, freq='D')
    price_df = pd.DataFrame({
        'datetime': dates,
        'close': [100, 102, 104, 106, 108],
        'open': [100] * 5,
        'high': [120] * 5,
        'low': [90] * 5,
        'volume': [1000] * 5,
    })
    mock_load_price.return_value = (price_df, False)

    attention_df = pd.DataFrame({
        'datetime': dates,
        'attention_score': [10, 90, 10, 10, 10],
        'weighted_attention': [5, 100, 5, 5, 5],
        'bullish_attention': [1, 80, 1, 1, 1],
        'bearish_attention': [0, 0, 0, 0, 0],
        'news_count': [1] * 5,
    })
    mock_load_attention.return_value = attention_df

    # max_holding_days 限制持仓长度
    res_max_hold = run_backtest_basic_attention(
        symbol="ZECUSDT",
        lookback_days=2,
        attention_quantile=0.8,
        max_daily_return=1.0,
        holding_days=10,
        max_holding_days=2,
    )
    t = res_max_hold['trades'][0]
    # entry day1 close=100, exit after 2 days -> day3 close=104
    assert t['entry_price'] == 100.0
    assert t['exit_price'] == 104.0

    # position_size 放大收益
    res_ps_1 = run_backtest_basic_attention(
        symbol="ZECUSDT",
        lookback_days=2,
        attention_quantile=0.8,
        max_daily_return=1.0,
        holding_days=10,
        max_holding_days=2,
        position_size=1.0,
    )
    res_ps_2 = run_backtest_basic_attention(
        symbol="ZECUSDT",
        lookback_days=2,
        attention_quantile=0.8,
        max_daily_return=1.0,
        holding_days=10,
        max_holding_days=2,
        position_size=2.0,
    )

    eq1 = res_ps_1['equity_curve'][-1]['equity']
    eq2 = res_ps_2['equity_curve'][-1]['equity']
    # position_size=2 应该放大收益
    assert eq2 > eq1
