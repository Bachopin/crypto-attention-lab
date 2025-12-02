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
    """增量获取 Google Trends 日度序列（使用 attention_features 作为缓存来源）

    逻辑：
    1. 如果 force_refresh=True：忽略缓存，直接全量抓取 start~end
    2. 否则：查询 attention_features 已有的 google_trend_value 范围
       - 若缓存为空：全量抓取 start~end
       - 若缓存已覆盖 end（最后一天存在）：直接返回缓存对应列
       - 否则：仅抓取 (latest_cached+1) ~ end 缺失区间，再与已有数据合并

    返回格式：DataFrame[datetime, value]
    """
    symbol = symbol.upper()
    cfg = get_symbol_attention_config(symbol)
    start = _normalize_datetime(start)
    end = _normalize_datetime(end)

    existing_df = pd.DataFrame()
    if USE_DATABASE and not force_refresh:
        try:
            db = get_db()
            existing_df = db.get_attention_features(symbol, start=start, end=end, timeframe='D')
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Failed to load existing attention_features for %s: %s", symbol, e)
            existing_df = pd.DataFrame()

    # 标准化已有数据
    if not existing_df.empty and 'datetime' in existing_df.columns:
        existing_df['datetime'] = pd.to_datetime(existing_df['datetime'], utc=True).dt.normalize()
        existing_df = existing_df.drop_duplicates(subset=['datetime'], keep='last').sort_values('datetime')

    # 判定是否需要增量抓取
    need_fetch = True
    fetch_start = start
    if force_refresh:
        need_fetch = True
    elif existing_df.empty:
        need_fetch = True
    else:
        latest_cached = existing_df['datetime'].max()
        if latest_cached >= end:  # 已覆盖所需范围
            need_fetch = False
        else:
            fetch_start = latest_cached + pd.Timedelta(days=1)
            # 如果增量区间起点超过 end 说明已覆盖
            if fetch_start > end:
                need_fetch = False

    fetched_df = pd.DataFrame()
    if need_fetch:
        fetched_df = fetch_google_trends_for_symbol(symbol, fetch_start, end, geo=cfg.google_geo)
        if not fetched_df.empty:
            fetched_df = _ensure_datetime_column(fetched_df)
            fetched_df = fetched_df.drop_duplicates(subset=['datetime'], keep='last').sort_values('datetime')

    # 合并：以已有数据优先（避免覆盖历史经过校验的值）
    if existing_df.empty:
        combined = fetched_df
    elif fetched_df.empty:
        combined = existing_df[['datetime', 'google_trend_value']].rename(columns={'google_trend_value': 'value'})
    else:
        # 统一列名后 concat 并去重
        ex = existing_df[['datetime', 'google_trend_value']].rename(columns={'google_trend_value': 'value'})
        new = fetched_df[['datetime', 'value']] if 'value' in fetched_df.columns else fetched_df[['datetime']].assign(value=fetched_df.get('value'))
        combined = pd.concat([ex, new], ignore_index=True)
        combined = combined.drop_duplicates(subset=['datetime'], keep='last').sort_values('datetime')

    if combined.empty:
        return pd.DataFrame(columns=['datetime', 'value'])

    # 只截取所需区间
    mask = (combined['datetime'] >= start) & (combined['datetime'] <= end)
    out = combined.loc[mask].copy()
    return out[['datetime', 'value']].reset_index(drop=True)
