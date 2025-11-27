from dataclasses import dataclass
from typing import List, Dict, Optional
import pandas as pd
from src.config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR


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
    # 价格与注意力
    price_path = RAW_DATA_DIR / f"price_{symbol}_1d.csv"
    att_path = PROCESSED_DATA_DIR / "attention_features_zec.csv"
    if not price_path.exists() or not att_path.exists():
        return {"error": "missing data"}
    p = pd.read_csv(price_path)
    a = pd.read_csv(att_path)
    p['datetime'] = pd.to_datetime(p['datetime'], utc=True, errors='coerce')
    a['datetime'] = pd.to_datetime(a['datetime'], utc=True, errors='coerce')
    df = pd.merge(p[['datetime', 'close']], a[['datetime', 'attention_score', 'weighted_attention', 'bullish_attention', 'bearish_attention']], on='datetime', how='inner')
    df = df.dropna()
    if start:
        df = df[df['datetime'] >= start]
    if end:
        df = df[df['datetime'] <= end]

    # 分位数阈值
    def rolling_q(s: pd.Series) -> pd.Series:
        return s.rolling(lookback_days, min_periods=5).apply(lambda x: pd.Series(x).quantile(attention_quantile), raw=False)

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
