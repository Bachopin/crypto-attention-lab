import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
import pandas as pd
from src.config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.services.market_data_service import MarketDataService
from src.backtest.strategy_templates import (
    AttentionCondition,
    build_attention_signal_series,
)

logger = logging.getLogger(__name__)


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
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    max_holding_days: Optional[int] = None,
    position_size: float = 1.0,
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
    attention_source: str = "legacy",
    attention_condition: Optional[AttentionCondition] = None,
) -> Dict:
    # 数据库优先加载
    source_key = (attention_source or "legacy").lower()
    if source_key not in {"legacy", "composite"}:
        source_key = "legacy"

    # 使用 MarketDataService 获取对齐的数据
    df = MarketDataService.get_aligned_data(symbol, start=start, end=end, timeframe='1d')
    
    if df.empty:
        return {"error": "missing data", "meta": {"attention_source": source_key}}
    
    # 确保 datetime 列存在 (MarketDataService 返回的 df 包含 datetime 列)
    if 'datetime' not in df.columns:
        # 如果 datetime 是索引，重置索引
        df = df.reset_index()
    
    # 过滤掉没有价格数据的行 (MarketDataService 是 left join on price，所以应该都有价格，但可能有 NaN)
    df = df.dropna(subset=['close'])

    signal_column = 'weighted_attention' if source_key == 'legacy' else 'composite_attention_score'

    if signal_column not in df.columns:
        logger.warning(
            "Requested attention source column missing: %s (symbol=%s, source=%s)",
            signal_column,
            symbol,
            source_key,
        )
        return {"error": f"{signal_column} not available", "meta": {"attention_source": source_key}}

    df['attention_signal'] = df[signal_column].astype(float)
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)

    condition_flags = None
    if attention_condition is not None:
        try:
            condition_series = build_attention_signal_series(
                symbol=symbol,
                condition=attention_condition,
                start=start,
                end=end,
                attention_df=df
            )
        except ValueError as exc:
            logger.warning("Attention condition build failed: %s", exc)
            return {
                "error": str(exc),
                "meta": {
                    "attention_source": source_key,
                    "attention_condition": attention_condition.to_dict(),
                },
            }

        datetime_index = pd.Index(df['datetime'])
        aligned = condition_series.reindex(datetime_index, fill_value=0).astype(int)
        df['attention_condition_signal'] = aligned.to_numpy()
        condition_flags = df['attention_condition_signal']

    # 分位数阈值
    def rolling_q(s: pd.Series) -> pd.Series:
        min_p = min(lookback_days, 5)
        return s.rolling(lookback_days, min_periods=min_p).apply(lambda x: pd.Series(x).quantile(attention_quantile), raw=False)

    df['w_q'] = rolling_q(df['attention_signal'])
    df['prev_close'] = df['close'].shift(1)
    df['daily_ret'] = (df['close'] / df['prev_close'] - 1.0).fillna(0)

    trades: List[Trade] = []
    i = 0
    while i < len(df):
        row = df.iloc[i]
        if attention_condition is not None:
            signal_hit = bool(condition_flags.iloc[i]) if condition_flags is not None else False
        else:
            signal_hit = pd.notna(row['w_q']) and row['attention_signal'] > row['w_q']

        cond = (
            signal_hit and
            row['daily_ret'] <= max_daily_return and
            (row.get('bullish_attention', 0) >= row.get('bearish_attention', 0))
        )
        if cond:
            entry_idx = i
            entry = df.iloc[entry_idx]
            entry_close = float(entry['close'])
            prev_close = entry.get('prev_close')
            entry_price = entry_close
            if pd.notna(prev_close) and entry_close > float(prev_close):
                entry_price = float(prev_close)

            # 动态持仓天数：优先使用 max_holding_days
            if max_holding_days is not None:
                future_bars = max(1, int(max_holding_days) - 1)
            else:
                future_bars = max(1, int(holding_days))
            exit_idx = entry_idx
            max_price_since_entry = entry_price
            ret = 0.0

            # 向前模拟持仓（包含信号当日），直到触发止损/止盈或达到最大持仓天数
            for step in range(0, future_bars + 1):
                idx = entry_idx + step
                if idx >= len(df):
                    break
                exit_idx = idx
                exit_row = df.iloc[idx]
                price_now = float(exit_row['close'])
                ret = price_now / entry_price - 1.0

                # 浮动回撤：基于入场以来的最高价
                max_price_since_entry = max(max_price_since_entry, price_now)
                drawdown = price_now / max_price_since_entry - 1.0

                stop = False
                if stop_loss_pct is not None and drawdown <= stop_loss_pct:
                    stop = True
                if take_profit_pct is not None and ret >= take_profit_pct:
                    stop = True

                if stop or step == future_bars:
                    break

            exit = df.iloc[exit_idx]
            trades.append(Trade(entry['datetime'], exit['datetime'], entry_price, float(exit['close']), float(ret)))
            i = exit_idx + 1
        else:
            i += 1

    # 统计
    equity = []
    eq = 1.0
    for t in trades:
        eq *= (1.0 + t.return_pct * position_size)
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

    # 最大连续亏损笔数
    max_consecutive_losses = 0
    current_losses = 0
    for t in trades:
        if t.return_pct < 0:
            current_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, current_losses)
        else:
            current_losses = 0

    # 按月聚合收益
    monthly_returns: Dict[str, float] = {}
    for t in trades:
        month_key = t.exit_date.strftime("%Y-%m")
        monthly_returns.setdefault(month_key, 0.0)
        monthly_returns[month_key] += t.return_pct * position_size

    summary = {
        "total_trades": len(trades),
        "win_rate": (wins / len(trades) * 100.0) if trades else 0.0,
        "avg_return": avg_ret,
        "cumulative_return": cumulative,
        "max_drawdown": max_dd,
        "max_consecutive_losses": max_consecutive_losses,
        "monthly_returns": monthly_returns,
    }

    if attention_condition is not None:
        summary["attention_condition"] = attention_condition.to_dict()

    meta = {
        "attention_source": source_key,
        "signal_field": signal_column,
    }
    if attention_condition is not None:
        meta["attention_condition"] = attention_condition.to_dict()

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
        "meta": meta,
    }
