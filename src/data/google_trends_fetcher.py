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
from src.data.db_storage import USE_DATABASE, get_db

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


def _ensure_datetime_column(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "datetime" not in df.columns:
        return df
    out = df.copy()
    out["datetime"] = pd.to_datetime(out["datetime"], utc=True, errors="coerce").dt.normalize()
    out = out.dropna(subset=["datetime"])
    return out


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


def fetch_google_trends_for_symbol(
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    freq: str = "D",
    geo: Optional[str] = None,
) -> pd.DataFrame:
    """Convenience wrapper that applies symbol-level keyword settings."""

    cfg = get_symbol_attention_config(symbol)
    series = fetch_google_trends(
        cfg.google_trends_keywords,
        start,
        end,
        geo=geo or cfg.google_geo,
    )
    if series.empty:
        return series
    series = _ensure_datetime_column(series)
    series["symbol"] = symbol.upper()
    series["keyword_set"] = "|".join(cfg.google_trends_keywords)
    return series


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


def get_google_trends_series(
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Return cached trends and fetch missing ranges if necessary."""

    cfg = get_symbol_attention_config(symbol)
    start = _normalize_datetime(start)
    end = _normalize_datetime(end)

    cached = pd.DataFrame()
    if not force_refresh:
        cached = _ensure_datetime_column(load_cached_google_trends(symbol))

    db_rows = pd.DataFrame()
    db_handle = None
    if USE_DATABASE:
        try:
            db_handle = get_db()
            db_rows = _ensure_datetime_column(db_handle.get_google_trends(symbol, start, end))
        except Exception as exc:  # pragma: no cover - DB optional
            logger.warning("Failed to load Google Trends rows from DB for %s: %s", symbol, exc)
            db_handle = None

    combined_existing = pd.concat(
        [df for df in (cached, db_rows) if not df.empty],
        ignore_index=True,
    )
    if not combined_existing.empty:
        combined_existing = (
            combined_existing
            .drop_duplicates(subset=["datetime"], keep="last")
            .sort_values("datetime")
        )

    coverage_ok = (
        not force_refresh
        and not combined_existing.empty
        and combined_existing["datetime"].min() <= start
        and combined_existing["datetime"].max() >= end
    )

    need_fetch = force_refresh or not coverage_ok
    fetched = pd.DataFrame()
    if need_fetch:
        fetched = fetch_google_trends_for_symbol(symbol, start, end, geo=cfg.google_geo)
        if fetched.empty:
            logger.warning(
                "Google Trends fetch returned empty for %s (keywords=%s)",
                symbol,
                cfg.google_trends_keywords,
            )
        else:
            if db_handle is None and USE_DATABASE:
                try:
                    db_handle = get_db()
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to init DB handle for google trends: %s", exc)
                    db_handle = None

            if db_handle is not None:
                try:
                    db_handle.save_google_trends(symbol, fetched.to_dict("records"))
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to persist Google Trends rows for %s: %s", symbol, exc)

    merged = pd.concat(
        [df for df in (combined_existing, fetched) if not df.empty],
        ignore_index=True,
    )

    if merged.empty:
        return merged

    merged = (
        merged
        .drop_duplicates(subset=["datetime"], keep="last")
        .sort_values("datetime")
    )

    save_google_trends_cache(symbol, merged[["datetime", "value"]])

    mask = (merged["datetime"] >= start) & (merged["datetime"] <= end)
    return merged.loc[mask].copy()
