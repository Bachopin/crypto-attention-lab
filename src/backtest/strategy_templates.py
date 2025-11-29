import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Literal, Optional

import pandas as pd

from src.data.db_storage import load_attention_data

logger = logging.getLogger(__name__)

ATTENTION_COLUMN_MAP = {
    "composite": "composite_attention_score",
    "news_channel": "news_channel_score",
}


@dataclass
class AttentionCondition:
    source: Literal["composite", "news_channel"] = "composite"
    regime: Literal["low", "mid", "high", "custom"] = "high"
    lower_quantile: Optional[float] = None
    upper_quantile: Optional[float] = None
    lookback_days: int = 30

    def __post_init__(self) -> None:
        self.source = (self.source or "composite").lower()
        self.regime = (self.regime or "high").lower()

        if self.source not in ATTENTION_COLUMN_MAP:
            raise ValueError(f"Unsupported attention source: {self.source}")

        if self.regime not in {"low", "mid", "high", "custom"}:
            raise ValueError(f"Unsupported regime: {self.regime}")

        self.lookback_days = int(self.lookback_days)
        if self.lookback_days <= 0:
            raise ValueError("lookback_days must be positive")

        for attr in ("lower_quantile", "upper_quantile"):
            value = getattr(self, attr)
            if value is None:
                continue
            if not (0.0 <= float(value) <= 1.0):
                raise ValueError(f"{attr} must be within [0, 1]")
            setattr(self, attr, float(value))

        if self.regime == "custom":
            if self.lower_quantile is None and self.upper_quantile is None:
                raise ValueError("Custom regime requires lower_quantile and/or upper_quantile")
        else:
            # Ignore user provided quantiles when using predefined regimes
            self.lower_quantile = None
            self.upper_quantile = None

        if self.lower_quantile is not None and self.upper_quantile is not None:
            if self.lower_quantile >= self.upper_quantile:
                raise ValueError("lower_quantile must be smaller than upper_quantile")

    def to_dict(self) -> dict:
        return asdict(self)


def _resolve_symbol(symbol: str) -> str:
    return symbol.replace("USDT", "") if symbol.upper().endswith("USDT") else symbol


def _resolve_bounds(condition: AttentionCondition) -> tuple[Optional[float], Optional[float]]:
    if condition.regime == "low":
        return 0.0, 1.0 / 3.0
    if condition.regime == "mid":
        return 1.0 / 3.0, 2.0 / 3.0
    if condition.regime == "high":
        return 2.0 / 3.0, 1.0
    # custom regime
    lower = condition.lower_quantile if condition.lower_quantile is not None else 0.0
    upper = condition.upper_quantile if condition.upper_quantile is not None else 1.0
    return lower, upper


def _get_attention_dataframe(
    symbol: str,
    condition: AttentionCondition,
    start: Optional[datetime],
    end: Optional[datetime],
    attention_df: Optional[pd.DataFrame],
) -> pd.DataFrame:
    if attention_df is not None:
        return attention_df.copy()

    fetch_start = None
    if start is not None:
        start_ts = pd.to_datetime(start, utc=True)
        buffer_days = max(condition.lookback_days * 2, 10)
        fetch_start = start_ts - pd.Timedelta(days=buffer_days)
    else:
        fetch_start = start

    df = load_attention_data(symbol, fetch_start, end)
    if df is None:
        return pd.DataFrame()
    return df.copy()


def build_attention_signal_series(
    symbol: str,
    condition: AttentionCondition,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    attention_df: Optional[pd.DataFrame] = None,
) -> pd.Series:
    """根据 AttentionCondition 构建 0/1 信号序列。"""
    if condition is None:
        raise ValueError("AttentionCondition is required")

    resolved_symbol = _resolve_symbol(symbol)
    df = _get_attention_dataframe(resolved_symbol, condition, start, end, attention_df)
    if df.empty:
        logger.warning("No attention data available for %s", resolved_symbol)
        return pd.Series(dtype=int)

    signal_column = ATTENTION_COLUMN_MAP.get(condition.source, condition.source)
    if signal_column not in df.columns:
        raise ValueError(f"Attention column '{signal_column}' not found for symbol {resolved_symbol}")

    df = df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    df = df.sort_values('datetime').dropna(subset=[signal_column])
    df = df.set_index('datetime')

    signal_series = df[signal_column].astype(float)
    window = max(1, int(condition.lookback_days))
    min_periods = min(window, 5)
    lower_bound, upper_bound = _resolve_bounds(condition)

    lower_threshold = None
    upper_threshold = None

    if lower_bound is not None:
        lower_threshold = signal_series.rolling(window, min_periods=min_periods).quantile(lower_bound)
    if upper_bound is not None:
        upper_threshold = signal_series.rolling(window, min_periods=min_periods).quantile(upper_bound)

    mask = signal_series.notna()
    if lower_threshold is not None:
        mask &= signal_series >= lower_threshold
    if upper_threshold is not None:
        mask &= signal_series <= upper_threshold

    flags = mask.astype(int)

    if start is not None:
        start_ts = pd.to_datetime(start, utc=True)
        flags = flags[flags.index >= start_ts]
    if end is not None:
        end_ts = pd.to_datetime(end, utc=True)
        flags = flags[flags.index <= end_ts]

    return flags
