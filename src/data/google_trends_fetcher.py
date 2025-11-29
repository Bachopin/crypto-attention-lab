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
    """Fetch raw Google Trends interest-over-time series.
    
    Google Trends API 限制:
    - ≤269天: 返回每日数据
    - >269天: 返回每周数据
    
    为确保始终获得每日数据，当时间跨度 >269天 时，会自动分段拉取。
    """

    if TrendReq is None:
        logger.warning("pytrends not installed; Google Trends channel will be empty")
        return pd.DataFrame(columns=["datetime", "value"])

    # 计算时间跨度
    total_days = (end - start).days
    
    # 如果 ≤269天，直接单次请求
    if total_days <= 269:
        return _fetch_single_chunk(keywords, start, end, geo)
    
    # 否则分段拉取以确保每日数据
    logger.info("Time span %d days > 269, fetching in chunks to ensure daily granularity", total_days)
    return _fetch_chunked(keywords, start, end, geo, chunk_days=269)


def _fetch_single_chunk(
    keywords: List[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    geo: str = "GLOBAL",
) -> pd.DataFrame:
    """单次请求获取 Google Trends 数据（≤269天）"""
    
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
    # 使用最大值而非平均值聚合多个关键词
    # 原因：不同别名可能覆盖不同受众，取最大值反映峰值关注度
    series = data.max(axis=1)
    df = pd.DataFrame({"datetime": series.index.normalize(), "value": series.values})
    df = df.groupby("datetime", as_index=False).max()
    return df


def _fetch_chunked(
    keywords: List[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    geo: str = "GLOBAL",
    chunk_days: int = 269,
) -> pd.DataFrame:
    """分段拉取以确保每日粒度
    
    Args:
        keywords: 搜索关键词列表
        start: 起始日期
        end: 结束日期
        geo: 地理位置过滤
        chunk_days: 每段天数，默认269（Google Trends 每日数据的最大范围）
    
    Returns:
        合并后的每日数据 DataFrame
    """
    from datetime import timedelta
    
    chunks = []
    current_start = start
    chunk_num = 0
    
    while current_start < end:
        chunk_num += 1
        current_end = min(current_start + pd.Timedelta(days=chunk_days), end)
        
        logger.debug("Fetching chunk %d: %s to %s", chunk_num, current_start.date(), current_end.date())
        
        chunk_data = _fetch_single_chunk(keywords, current_start, current_end, geo)
        
        if not chunk_data.empty:
            chunks.append(chunk_data)
        
        # 移动到下一段
        current_start = current_end
    
    if not chunks:
        logger.warning("All chunks failed for Google Trends fetch")
        return pd.DataFrame(columns=["datetime", "value"])
    
    # 合并所有段
    merged = pd.concat(chunks, ignore_index=True)
    
    # 去重并排序
    merged = merged.drop_duplicates(subset=["datetime"], keep="first")
    merged = merged.sort_values("datetime").reset_index(drop=True)
    
    logger.info("Merged %d chunks into %d daily data points", len(chunks), len(merged))
    
    return merged


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

    db_rows = pd.DataFrame()
    db_handle = None
    
    # Always try to get DB handle
    try:
        db_handle = get_db()
    except Exception as exc:
        logger.warning("Failed to init DB handle for google trends: %s", exc)
        db_handle = None

    if not force_refresh and db_handle:
        try:
            db_rows = _ensure_datetime_column(db_handle.get_google_trends(symbol, start, end))
        except Exception as exc:
            logger.warning("Failed to load Google Trends rows from DB for %s: %s", symbol, exc)

    coverage_ok = (
        not force_refresh
        and not db_rows.empty
        and db_rows["datetime"].min() <= start
        and db_rows["datetime"].max() >= end
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
            if db_handle:
                try:
                    db_handle.save_google_trends(symbol, fetched.to_dict("records"))
                except Exception as exc:
                    logger.warning("Failed to persist Google Trends rows for %s: %s", symbol, exc)

    # Merge fetched data with existing DB data (if any)
    dfs_to_merge = [df for df in (db_rows, fetched) if not df.empty]
    if not dfs_to_merge:
        return pd.DataFrame()
    
    merged = pd.concat(dfs_to_merge, ignore_index=True)

    merged = (
        merged
        .drop_duplicates(subset=["datetime"], keep="last")
        .sort_values("datetime")
    )

    mask = (merged["datetime"] >= start) & (merged["datetime"] <= end)
    return merged.loc[mask].copy()
