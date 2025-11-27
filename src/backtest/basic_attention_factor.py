from dataclasses import dataclass
from typing import List, Dict, Optional
import pandas as pd
from src.config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.data.db_storage import load_price_data, load_attention_data


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    return_pct: float


def run_backtest_basic_attention(
    symbol: str = "ZECUSDT",
    lookback_days: int = 30,
    attention_quantile: float = 0.8,
    max_daily_return: float = 0.05,
    holding_days: int = 3,
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
) -> Dict:
    # 数据库优先加载
    p_df, _ = load_price_data(symbol, '1d', start, end)
    a_df = load_attention_data(symbol.replace('USDT', ''), start, end)
    
    if p_df.empty or a_df.empty:
        return {"error": "missing data"}
    
    df = pd.merge(
        p_df[['datetime', 'close']],
        a_df[['datetime', 'attention_score', 'weighted_attention', 'bullish_attention', 'bearish_attention']],
        on='datetime',
        how='inner'
    )
    df = df.dropna()

    # 分位数阈值
    def rolling_q(s: pd.Series) -> pd.Series:
        min_p = min(lookback_days, 5)
        return s.rolling(lookback_days, min_periods=min_p).apply(lambda x: pd.Series(x).quantile(attention_quantile), raw=False)

    df['w_q'] = rolling_q(df['weighted_attention'])
    df['prev_close'] = df['close'].shift(1)
    df['daily_ret'] = (df['close'] / df['prev_close'] - 1.0).fillna(0)

    trades: List[Trade] = []
    i = 0
    while i < len(df):
        row = df.iloc[i]
        cond = (
            pd.notna(row['w_q']) and row['weighted_attention'] >= row['w_q'] and
            row['daily_ret'] <= max_daily_return and
            (row.get('bullish_attention', 0) >= row.get('bearish_attention', 0))
        )
        if cond:
            entry_idx = i
            exit_idx = min(i + holding_days, len(df) - 1)
            entry = df.iloc[entry_idx]
            exit = df.iloc[exit_idx]
            ret = (exit['close'] / entry['close'] - 1.0)
            trades.append(Trade(entry['datetime'], exit['datetime'], float(entry['close']), float(exit['close']), float(ret)))
            i = exit_idx + 1
        else:
            i += 1

    # 统计
    equity = []
    eq = 1.0
    for t in trades:
        eq *= (1.0 + t.return_pct)
        equity.append({"datetime": t.exit_date.isoformat(), "equity": eq})

    if trades:
        wins = sum(1 for t in trades if t.return_pct > 0)
        avg_ret = sum(t.return_pct for t in trades) / len(trades)
        cumulative = eq - 1.0
    else:
        wins = 0
        avg_ret = 0.0
        cumulative = 0.0

    # 简易最大回撤（基于 equity 序列）
    max_dd = 0.0
    peak = 1.0
    for pt in equity:
        peak = max(peak, pt['equity'])
        dd = (peak - pt['equity']) / peak
        max_dd = max(max_dd, dd)

    summary = {
        "total_trades": len(trades),
        "win_rate": (wins / len(trades) * 100.0) if trades else 0.0,
        "avg_return": avg_ret,
        "cumulative_return": cumulative,
        "max_drawdown": max_dd,
    }

    return {
        "summary": summary,
        "trades": [
            {
                "entry_date": t.entry_date.isoformat(),
                "exit_date": t.exit_date.isoformat(),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "return_pct": t.return_pct,
            } for t in trades
        ],
        "equity_curve": equity,
    }
