"""
回测逻辑单元测试 - 优化版

使用共享 fixtures 和更高效的 mock 策略
"""
import pytest
import pandas as pd
from unittest.mock import patch
from src.backtest.basic_attention_factor import run_backtest_basic_attention


class TestBasicAttentionBacktest:
    """基础注意力回测测试"""

    @pytest.fixture
    def price_data(self) -> pd.DataFrame:
        """测试用价格数据"""
        dates = pd.date_range(start='2025-01-01', periods=10, freq='D')
        return pd.DataFrame({
            'datetime': dates,
            'close': [100, 101, 102, 100, 105, 110, 108, 112, 115, 120],
            'open': [100] * 10,
            'high': [120] * 10,
            'low': [90] * 10,
            'volume': [1000] * 10
        })

    @pytest.fixture
    def attention_data(self) -> pd.DataFrame:
        """测试用注意力数据"""
        dates = pd.date_range(start='2025-01-01', periods=10, freq='D')
        return pd.DataFrame({
            'datetime': dates,
            'attention_score': [10, 10, 10, 80, 10, 10, 10, 10, 10, 10],
            'weighted_attention': [6, 4, 5, 50, 5, 5, 5, 5, 5, 5],
            'bullish_attention': [1, 1, 1, 40, 1, 1, 1, 1, 1, 1],
            'bearish_attention': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            'news_count': [1] * 10
        })

    @patch('src.backtest.basic_attention_factor.load_price_data')
    @patch('src.backtest.basic_attention_factor.load_attention_data')
    def test_run_backtest_basic_attention(self, mock_load_attention, mock_load_price,
                                          price_data, attention_data):
        mock_load_price.return_value = (price_data, False)
        mock_load_attention.return_value = attention_data

        result = run_backtest_basic_attention(
            symbol="ZECUSDT",
            lookback_days=3,
            attention_quantile=0.8,
            max_daily_return=0.05,
            holding_days=2
        )

        assert "summary" in result
        assert "trades" in result
        assert "equity_curve" in result
        
        trades = result['trades']
        assert len(trades) >= 1
        trade = trades[0]
        assert trade['entry_price'] == 100.0
        assert trade['exit_price'] == 110.0
        assert trade['return_pct'] == pytest.approx(0.10)

        summary = result['summary']
        assert summary['total_trades'] >= 1
        assert summary['avg_return'] > 0


class TestStopLossAndTakeProfit:
    """止损止盈测试"""

    @pytest.fixture
    def sl_tp_price_data(self) -> pd.DataFrame:
        dates = pd.date_range(start='2025-01-01', periods=6, freq='D')
        return pd.DataFrame({
            'datetime': dates,
            'close': [100, 110, 90, 95, 80, 85],
            'open': [100] * 6,
            'high': [120] * 6,
            'low': [80] * 6,
            'volume': [1000] * 6,
        })

    @pytest.fixture
    def sl_tp_attention_data(self) -> pd.DataFrame:
        dates = pd.date_range(start='2025-01-01', periods=6, freq='D')
        return pd.DataFrame({
            'datetime': dates,
            'attention_score': [10, 90, 10, 10, 10, 10],
            'weighted_attention': [5, 100, 5, 5, 5, 5],
            'bullish_attention': [1, 80, 1, 1, 1, 1],
            'bearish_attention': [0, 0, 0, 0, 0, 0],
            'news_count': [1] * 6,
        })

    @patch('src.backtest.basic_attention_factor.load_price_data')
    @patch('src.backtest.basic_attention_factor.load_attention_data')
    def test_take_profit(self, mock_load_attention, mock_load_price,
                         sl_tp_price_data, sl_tp_attention_data):
        mock_load_price.return_value = (sl_tp_price_data, False)
        mock_load_attention.return_value = sl_tp_attention_data

        res_tp = run_backtest_basic_attention(
            symbol="ZECUSDT",
            lookback_days=2,
            attention_quantile=0.8,
            max_daily_return=1.0,
            holding_days=5,
            stop_loss_pct=None,
            take_profit_pct=0.05,
        )
        trades_tp = res_tp['trades']
        assert len(trades_tp) == 1
        t_tp = trades_tp[0]
        assert t_tp['entry_price'] == 100.0
        assert t_tp['exit_price'] == 110.0

    @patch('src.backtest.basic_attention_factor.load_price_data')
    @patch('src.backtest.basic_attention_factor.load_attention_data')
    def test_stop_loss(self, mock_load_attention, mock_load_price,
                       sl_tp_price_data, sl_tp_attention_data):
        mock_load_price.return_value = (sl_tp_price_data, False)
        mock_load_attention.return_value = sl_tp_attention_data

        res_sl = run_backtest_basic_attention(
            symbol="ZECUSDT",
            lookback_days=2,
            attention_quantile=0.8,
            max_daily_return=1.0,
            holding_days=5,
            stop_loss_pct=-0.10,
            take_profit_pct=None,
        )
        trades_sl = res_sl['trades']
        assert len(trades_sl) == 1
        t_sl = trades_sl[0]
        assert t_sl['entry_price'] == 100.0
        assert t_sl['exit_price'] in (90.0, 95.0)


class TestHoldingAndPositionSize:
    """持仓周期和仓位测试"""

    @pytest.fixture
    def position_price_data(self) -> pd.DataFrame:
        dates = pd.date_range(start='2025-01-01', periods=5, freq='D')
        return pd.DataFrame({
            'datetime': dates,
            'close': [100, 102, 104, 106, 108],
            'open': [100] * 5,
            'high': [120] * 5,
            'low': [90] * 5,
            'volume': [1000] * 5,
        })

    @pytest.fixture
    def position_attention_data(self) -> pd.DataFrame:
        dates = pd.date_range(start='2025-01-01', periods=5, freq='D')
        return pd.DataFrame({
            'datetime': dates,
            'attention_score': [10, 90, 10, 10, 10],
            'weighted_attention': [5, 100, 5, 5, 5],
            'bullish_attention': [1, 80, 1, 1, 1],
            'bearish_attention': [0, 0, 0, 0, 0],
            'news_count': [1] * 5,
        })

    @patch('src.backtest.basic_attention_factor.load_price_data')
    @patch('src.backtest.basic_attention_factor.load_attention_data')
    def test_max_holding_days(self, mock_load_attention, mock_load_price,
                              position_price_data, position_attention_data):
        mock_load_price.return_value = (position_price_data, False)
        mock_load_attention.return_value = position_attention_data

        res_max_hold = run_backtest_basic_attention(
            symbol="ZECUSDT",
            lookback_days=2,
            attention_quantile=0.8,
            max_daily_return=1.0,
            holding_days=10,
            max_holding_days=2,
        )
        t = res_max_hold['trades'][0]
        assert t['entry_price'] == 100.0
        assert t['exit_price'] == 104.0

    @patch('src.backtest.basic_attention_factor.load_price_data')
    @patch('src.backtest.basic_attention_factor.load_attention_data')
    def test_position_size_impact(self, mock_load_attention, mock_load_price,
                                   position_price_data, position_attention_data):
        mock_load_price.return_value = (position_price_data, False)
        mock_load_attention.return_value = position_attention_data

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
        assert eq2 > eq1
