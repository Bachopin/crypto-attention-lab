"""Google Trends ingress helpers.

This module intentionally keeps the implementation lightweight:
- When pytrends is available we request the interest-over-time series
- Results are cached under data/processed for reuse by attention features
- When pytrends is missing (or rate-limited), callers receive an empty
  DataFrame and upstream components gracefully fallback to zeros
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd

from src.config.attention_channels import get_symbol_attention_config
from src.config.settings import PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

try:
    from pytrends.request import TrendReq  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    TrendReq = None

CACHE_FILENAME_TEMPLATE = "google_trends_{symbol}.csv"


def _cache_path(symbol: str):
    return PROCESSED_DATA_DIR / CACHE_FILENAME_TEMPLATE.format(symbol=symbol.lower())


def _normalize_datetime(value: pd.Timestamp | datetime) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.normalize()


def fetch_google_trends(
    keywords: List[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    geo: str = "GLOBAL",
) -> pd.DataFrame:
    """Fetch raw Google Trends interest-over-time series."""

    if TrendReq is None:
        logger.warning("pytrends not installed; Google Trends channel will be empty")
        return pd.DataFrame(columns=["datetime", "value"])

    timeframe = f"{start.strftime('%Y-%m-%d')} {end.strftime('%Y-%m-%d')}"
    geo_param = "" if geo.upper() == "GLOBAL" else geo

    pytrends = TrendReq(hl="en-US", tz=0)
    try:
        pytrends.build_payload(keywords, timeframe=timeframe, geo=geo_param)
        data = pytrends.interest_over_time()
    except Exception as exc:  # pragma: no cover - network failure
        logger.warning("Google Trends fetch failed: %s", exc)
        return pd.DataFrame(columns=["datetime", "value"])

    if data.empty:
        return pd.DataFrame(columns=["datetime", "value"])

    data = data.drop(columns=[c for c in data.columns if c.lower() == "ispartial"], errors="ignore")
    data.index = pd.to_datetime(data.index, utc=True)
    series = data.mean(axis=1)
    df = pd.DataFrame({"datetime": series.index.normalize(), "value": series.values})
    df = df.groupby("datetime", as_index=False).mean()
    return df


def load_cached_google_trends(symbol: str) -> pd.DataFrame:
    path = _cache_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=["datetime", "value"])
    df = pd.read_csv(path)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.normalize()
    return df


def save_google_trends_cache(symbol: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    path = _cache_path(symbol)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def get_google_trends_series(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Return cached trends and fetch missing ranges if necessary."""

    cfg = get_symbol_attention_config(symbol)
    start = _normalize_datetime(start)
    end = _normalize_datetime(end)

    cached = load_cached_google_trends(symbol)
    coverage_ok = (not cached.empty) and cached["datetime"].min() <= start and cached["datetime"].max() >= end

    if not coverage_ok:
        fetched = fetch_google_trends(cfg.google_trends_keywords, start, end, geo=cfg.google_geo)
        if not fetched.empty:
            combined = pd.concat([cached, fetched], ignore_index=True)
            combined = combined.drop_duplicates(subset=["datetime"], keep="last").sort_values("datetime")
            save_google_trends_cache(symbol, combined)
            cached = combined
        else:
            logger.debug("Google Trends fetch returned empty for %s", symbol)

    if cached.empty:
        return cached

    mask = (cached["datetime"] >= start) & (cached["datetime"] <= end)
    return cached.loc[mask].copy()
