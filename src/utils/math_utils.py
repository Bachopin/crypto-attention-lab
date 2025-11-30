"""
Math utilities for financial time series analysis.
"""
import numpy as np
import pandas as pd
from typing import Any

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float, handling None/NaN/Inf."""
    if value is None:
        return default
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default

def compute_zscore(value: float, mean: float, std: float) -> float:
    """
    Calculate z-score, handling zero standard deviation.
    
    Returns:
        (value - mean) / std, or 0.0 if std is 0/NaN/None.
    """
    if std == 0 or np.isnan(std) or std is None:
        return 0.0
    return (value - mean) / std

def compute_log_return(prices: pd.Series) -> float:
    """
    Calculate cumulative log return: ln(P_end / P_start).
    """
    if prices.empty or len(prices) < 2:
        return 0.0
    
    start_price = prices.iloc[0]
    end_price = prices.iloc[-1]
    
    if start_price <= 0 or end_price <= 0:
        return 0.0
    
    return float(np.log(end_price / start_price))

def compute_volatility(prices: pd.Series) -> float:
    """
    Calculate volatility (standard deviation of log returns).
    """
    if prices.empty or len(prices) < 3:
        return 0.0
    
    log_returns = np.log(prices / prices.shift(1)).dropna()
    
    if log_returns.empty:
        return 0.0
    
    return float(log_returns.std(ddof=1))

def compute_slope(series: pd.Series) -> float:
    """
    Calculate linear trend slope using simple linear regression (y = a + bx).
    Returns b.
    """
    if series.empty or len(series) < 2:
        return 0.0
    
    # Remove NaNs
    clean = series.dropna()
    if len(clean) < 2:
        return 0.0
    
    x = np.arange(len(clean))
    y = clean.values
    
    try:
        slope, _ = np.polyfit(x, y, 1)
        return float(slope)
    except Exception:
        return 0.0

def compute_rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """
    Calculate rolling z-score.
    
    Args:
        series: Input pandas Series.
        window: Rolling window size.
        
    Returns:
        Series of z-scores, filled with 0.0 where undefined.
    """
    if series.empty:
        return series
        
    rolling = series.rolling(window=window, min_periods=max(5, window // 2))
    mean = rolling.mean()
    std = rolling.std(ddof=0)
    
    # Avoid division by zero
    std = std.replace(0, np.nan)
    
    z = (series - mean) / std
    return z.fillna(0.0)

def safe_pct_change(series: pd.Series, periods: int) -> pd.Series:
    """
    Calculate percentage change safely, handling division by zero and infs.
    
    Args:
        series: Input pandas Series.
        periods: Number of periods to shift.
        
    Returns:
        Series of percentage changes, filled with 0.0 where undefined.
    """
    if series.empty:
        return series
        
    prev = series.shift(periods)
    # Replace 0 in denominator with NaN to avoid inf, then fillna(0) later
    change = (series - prev) / prev.replace(0, np.nan)
    return change.replace([np.inf, -np.inf], np.nan).fillna(0.0)

def compute_rolling_quantile(series: pd.Series, window: int, quantile: float) -> pd.Series:
    """
    Calculate rolling quantile safely.
    
    Args:
        series: Input pandas Series.
        window: Rolling window size.
        quantile: Quantile to compute (0.0 to 1.0).
        
    Returns:
        Series of rolling quantiles.
    """
    if series.empty:
        return series
    
    # min_periods strategy: at least half the window, but minimum 5 (or window if smaller)
    min_periods = max(min(5, window), window // 2)
    return series.rolling(window=window, min_periods=min_periods).apply(
        lambda x: pd.Series(x).quantile(quantile), raw=False
    )

