"""Twitter / X public discussion volume ingestion helpers.

We intentionally keep the implementation simple: if a bearer token is
available the module calls the official counts endpoint, otherwise it
returns a zero-filled frame so downstream code can still function.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from src.config.attention_channels import get_symbol_attention_config
from src.config.settings import PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)

BASE_URL_RECENT = "https://api.twitter.com/2/tweets/counts/recent"
BASE_URL_ALL = "https://api.twitter.com/2/tweets/counts/all"
CACHE_FILENAME_TEMPLATE = "twitter_volume_{symbol}.csv"


def _cache_path(symbol: str):
    return PROCESSED_DATA_DIR / CACHE_FILENAME_TEMPLATE.format(symbol=symbol.lower())


def _normalize_datetime(value: pd.Timestamp | datetime) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.normalize()


def _request_counts(query: str, start: pd.Timestamp, end: pd.Timestamp, granularity: str) -> pd.DataFrame:
    token = os.getenv("TWITTER_BEARER_TOKEN")
    if not token:
        logger.warning("TWITTER_BEARER_TOKEN not configured; twitter channel will be zero-filled")
        return pd.DataFrame()

    delta_days = max(1, int((end - start).days))
    url = BASE_URL_RECENT if delta_days <= 7 else BASE_URL_ALL
    params = {
        "query": query,
        "granularity": granularity,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }

    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - network failure
        logger.warning("Twitter counts API failed: %s", exc)
        return pd.DataFrame()

    payload = resp.json().get("data", [])
    rows = []
    for item in payload:
        start_time = pd.to_datetime(item.get("start"), utc=True)
        rows.append({
            "datetime": start_time.normalize(),
            "tweet_count": item.get("tweet_count", 0),
        })
    return pd.DataFrame(rows)


def load_cached_twitter_volume(symbol: str) -> pd.DataFrame:
    path = _cache_path(symbol)
    if not path.exists():
        return pd.DataFrame(columns=["datetime", "tweet_count"])
    df = pd.read_csv(path)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.normalize()
    return df


def save_twitter_volume_cache(symbol: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    path = _cache_path(symbol)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def get_twitter_volume_series(
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    granularity: str = "day",
) -> pd.DataFrame:
    start = _normalize_datetime(start)
    end = _normalize_datetime(end)
    cfg = get_symbol_attention_config(symbol)

    cached = load_cached_twitter_volume(symbol)
    coverage_ok = (not cached.empty) and cached["datetime"].min() <= start and cached["datetime"].max() >= end

    if not coverage_ok:
        fetched = _request_counts(cfg.twitter_query, start, end + pd.Timedelta(days=1), granularity)
        if fetched.empty:
            # fallback to zero series so downstream z-scores are 0 instead of NaN
            idx = pd.date_range(start=start, end=end, freq="D", tz="UTC")
            fetched = pd.DataFrame({"datetime": idx.normalize(), "tweet_count": 0})
        combined = pd.concat([cached, fetched], ignore_index=True)
        combined = combined.drop_duplicates(subset=["datetime"], keep="last").sort_values("datetime")
        save_twitter_volume_cache(symbol, combined)
        cached = combined

    if cached.empty:
        return cached

    mask = (cached["datetime"] >= start) & (cached["datetime"] <= end)
    return cached.loc[mask].copy()
