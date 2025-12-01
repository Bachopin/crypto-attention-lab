from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime
import logging

from src.data.db_storage import load_attention_data as db_load_attention_data, load_price_data as db_load_price_data

logger = logging.getLogger(__name__)

def _get_attention_column(attention_source: str) -> str:
    mapping = {
        "composite": "composite_attention_score",
        "news_channel": "news_channel_score",
        "google_channel": "google_channel_score",
        "twitter_channel": "twitter_channel_score",
    }
    key = (attention_source or "").lower()
    return mapping.get(key, attention_source)


def _sanitize_lookahead_days(lookahead_days: List[int]) -> List[int]:
    try:
        cleaned = sorted({int(day) for day in lookahead_days if int(day) > 0})
    except (TypeError, ValueError):
        raise ValueError("lookahead_days must be positive integers") from None

    if not cleaned:
        raise ValueError("lookahead_days must contain at least one positive integer")
    return cleaned


def _normalize_split_method(split_method: str, split_quantiles: Optional[List[float]]) -> str:
    allowed = {"tercile", "quartile", "custom"}
    method = (split_method or "tercile").lower()
    if method not in allowed:
        raise ValueError(f"split_method must be one of {sorted(allowed)}")
    if method == "custom" and not split_quantiles:
        raise ValueError("split_quantiles is required when split_method='custom'")
    return method


def _compute_quantile_bins(series: pd.Series, split_method: str, split_quantiles: Optional[List[float]]) -> Tuple[np.ndarray, List[str]]:
    if split_quantiles:
        qs = sorted({float(q) for q in split_quantiles})
        if qs[0] > 0.0:
            qs.insert(0, 0.0)
        if qs[-1] < 1.0:
            qs.append(1.0)
    elif split_method == "tercile":
        qs = [0.0, 1 / 3, 2 / 3, 1.0]
    elif split_method == "quartile":
        qs = [0.0, 0.25, 0.5, 0.75, 1.0]
    else:
        raise ValueError("split_quantiles must be provided when split_method='custom'")

    if len(qs) < 2:
        raise ValueError("split_quantiles must define at least two cut points")

    quantiles = series.quantile(qs).to_numpy()
    # Ensure strictly increasing to avoid duplicates causing cut errors
    quantiles = np.unique(quantiles)
    if len(quantiles) < 2:
        raise ValueError("Insufficient variance in attention series to compute bins")

    n_bins = len(quantiles) - 1
    if n_bins == 3:
        labels = ["low", "mid", "high"]
    elif n_bins == 4:
        labels = ["q1", "q2", "q3", "q4"]
    else:
        labels = [f"q{i + 1}" for i in range(n_bins)]

    return quantiles, labels


def _max_drawdown_from_returns(returns: pd.Series) -> float:
    # Approximate MDD from cumulative log-return path
    cum = returns.cumsum()
    running_max = cum.cummax()
    drawdown = cum - running_max
    return float(drawdown.min()) if not drawdown.empty else 0.0


def _load_attention(symbol: str, start: Optional[datetime], end: Optional[datetime]) -> pd.DataFrame:
    df = db_load_attention_data(symbol, start, end)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df = df.sort_values('datetime').set_index('datetime')
    else:
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.sort_index()
    # Daily sample unify
    df = df.resample('1D').last().dropna(how='all')
    # Normalize index to date only (remove time component) for proper join
    df.index = df.index.normalize()
    return df


def _load_prices(symbol: str, start: Optional[datetime], end: Optional[datetime]) -> pd.DataFrame:
    symbol_code = symbol if symbol.endswith('USDT') else f"{symbol}USDT"
    df, _ = db_load_price_data(symbol_code, '1d', start, end)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df = df.sort_values('datetime').set_index('datetime')
    else:
        df.index = pd.to_datetime(df.index, utc=True)
        df = df.sort_index()
    if 'close' not in df.columns:
        for c in ['Close', 'closing_price', 'price']:
            if c in df.columns:
                df['close'] = df[c]
                break
    # Normalize index to date only (remove time component) for proper join
    df.index = df.index.normalize()
    return df[['close']].dropna()


def analyze_attention_regimes(
    symbols: List[str],
    lookahead_days: List[int],
    attention_source: str = "composite",
    split_method: str = "tercile",
    split_quantiles: Optional[List[float]] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict:
    """
    对多币种进行 Attention Regime 分析。

    返回结构适合直接 JSON 化，包含每个 symbol 在不同 Attention regime 下、
    对未来 k 天收益的统计信息。
    """
    if not symbols:
        raise ValueError("symbols must not be empty")

    sanitized_lookahead = _sanitize_lookahead_days(lookahead_days)
    method = _normalize_split_method(split_method, split_quantiles)

    results: Dict[str, Dict] = {}
    attention_col = _get_attention_column(attention_source)

    for symbol in symbols:
        # reuse storage instance inside loaders by monkey-patching if needed (simplify by passing instance)
        att = _load_attention(symbol, start, end)
        prices = _load_prices(symbol, start, end)

        if att.empty or prices.empty:
            results[symbol] = {
                "meta": {"error": "missing data"},
                "regimes": [],
            }
            continue

        if attention_col not in att.columns:
            results[symbol] = {
                "meta": {"error": f"attention column '{attention_col}' not found"},
                "regimes": [],
            }
            continue

        # Merge on date index
        # Join attention & price; avoid unnecessary copy
        df = att[[attention_col]].join(prices[["close"]], how="inner").dropna()
        if df.empty:
            results[symbol] = {
                "meta": {"error": "no overlapping attention and price data"},
                "regimes": [],
            }
            continue

        # Compute bins
        try:
            bin_edges, labels = _compute_quantile_bins(df[attention_col], method, split_quantiles)
        except Exception as e:
            results[symbol] = {
                "meta": {"error": f"failed to compute quantiles: {e}"},
                "regimes": [],
            }
            continue

        # Assign regimes
        # Use pandas.cut with include_lowest=True
        df["regime"] = pd.cut(df[attention_col], bins=bin_edges, labels=labels, include_lowest=True)
        df = df.dropna(subset=["regime"])  # drop where binning failed

        # Precompute future returns for all k
        close = df["close"]
        future_returns = {}
        for k in sanitized_lookahead:
            # log return from t close to t+k close
            shifted = close.shift(-k)
            r = np.log(shifted / close)
            future_returns[k] = r
        
        # Assemble stats by regime
        regime_list = []
        
        # We want to iterate through labels to maintain order (low -> high)
        for i, lab in enumerate(labels):
            subset = df[df["regime"] == lab]
            
            # Determine quantile range for this bin
            # bin_edges has length len(labels) + 1
            q_range = [float(bin_edges[i]), float(bin_edges[i+1])]
            
            stats_by_k = {}
            
            if subset.empty:
                for k in sanitized_lookahead:
                    stats_by_k[str(k)] = {
                        "avg_return": None,
                        "std_return": None,
                        "pos_ratio": None,
                        "sample_count": 0
                    }
            else:
                for k in sanitized_lookahead:
                    r = future_returns[k].loc[subset.index].dropna()
                    if r.empty:
                        stats_by_k[str(k)] = {
                            "avg_return": None,
                            "std_return": None,
                            "pos_ratio": None,
                            "sample_count": 0
                        }
                    else:
                        stats_by_k[str(k)] = {
                            "avg_return": float(r.mean()),
                            "std_return": float(r.std(ddof=1)) if len(r) > 1 else 0.0,
                            "pos_ratio": float((r > 0).mean()),
                            "sample_count": int(len(r)),
                        }
            
            regime_list.append({
                "name": lab,
                "quantile_range": q_range,
                "stats": stats_by_k
            })

        results[symbol] = {
            "meta": {
                "attention_source": attention_source,
                "split_method": method,
                "lookahead_days": sanitized_lookahead,
                "data_points": len(df)
            },
            "regimes": regime_list
        }

    return {
        "meta": {
            "symbols": symbols,
            "lookahead_days": sanitized_lookahead,
            "attention_source": attention_source,
            "split_method": method,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
        },
        "results": results
    }
