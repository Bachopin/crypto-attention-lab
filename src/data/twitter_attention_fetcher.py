"""Twitter / X public discussion volume ingestion helpers.

实现方案：
1. 方法 A（优先）：Twitter API v2 (需要 Bearer Token)
2. 方法 B（备选）：基于 CoinGecko followers 数据的智能估算
3. 方法 C（兜底）：高质量 mock 数据

方法 B 算法：
- 从 CoinGecko 获取真实 Twitter followers 数量
- 基于 followers 数量和活跃度系数估算每日讨论量
- 添加趋势、波动、周期性和随机事件
- 生成的数据具有统计真实性
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
import numpy as np
import requests

from src.config.attention_channels import get_symbol_attention_config
from src.config.settings import PROCESSED_DATA_DIR
from src.data.db_storage import USE_DATABASE, get_db

logger = logging.getLogger(__name__)

BASE_URL_RECENT = "https://api.twitter.com/2/tweets/counts/recent"
BASE_URL_ALL = "https://api.twitter.com/2/tweets/counts/all"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Symbol to CoinGecko ID mapping
SYMBOL_TO_COINGECKO_ID = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'BNB': 'binancecoin',
    'SOL': 'solana',
    'ADA': 'cardano',
    'XRP': 'ripple',
    'DOT': 'polkadot',
    'DOGE': 'dogecoin',
    'MATIC': 'matic-network',
    'LINK': 'chainlink',
    'UNI': 'uniswap',
    'LTC': 'litecoin',
    'AVAX': 'avalanche-2',
    'ATOM': 'cosmos',
    'XMR': 'monero',
    'ZEC': 'zcash',
}


def _normalize_datetime(value: pd.Timestamp | datetime) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.normalize()


def _request_counts(query: str, start: pd.Timestamp, end: pd.Timestamp, granularity: str) -> pd.DataFrame:
    """方法 A：使用 Twitter API v2"""
    token = os.getenv("TWITTER_BEARER_TOKEN")
    if not token:
        logger.info("TWITTER_BEARER_TOKEN not configured; will use alternative methods")
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
        logger.warning("Twitter API failed: %s", exc)
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


def _fetch_coingecko_followers(symbol: str) -> int:
    """从 CoinGecko 获取 Twitter followers 数量"""
    coin_id = SYMBOL_TO_COINGECKO_ID.get(symbol)
    if not coin_id:
        logger.debug(f"No CoinGecko ID for {symbol}")
        return 0
    
    url = f"{COINGECKO_API}/coins/{coin_id}"
    params = {
        'localization': 'false',
        'tickers': 'false',
        'market_data': 'false',
        'community_data': 'true',
        'developer_data': 'false',
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        community = data.get('community_data', {})
        followers = community.get('twitter_followers')
        
        if followers and followers > 0:
            logger.info(f"{symbol} Twitter followers from CoinGecko: {followers:,}")
            return int(followers)
        
        return 0
        
    except Exception as e:
        logger.debug(f"CoinGecko API error for {symbol}: {e}")
        return 0


def _generate_volume_from_followers(
    symbol: str,
    followers: int,
    start: pd.Timestamp,
    end: pd.Timestamp
) -> pd.DataFrame:
    """
    方法 B：基于 Twitter followers 数量生成智能估算
    
    算法：
    1. 活跃度系数根据 followers 规模动态调整
    2. 大项目（>100万）：5% 活跃度
    3. 中项目（10万-100万）：8% 活跃度
    4. 小项目（<10万）：12% 活跃度
    5. 添加趋势、随机波动、周期性、突发事件
    """
    date_range = pd.date_range(start=start, end=end, freq='D', tz='UTC')
    
    # 动态活跃度系数
    if followers > 1000000:
        activity_rate = 0.05
    elif followers > 100000:
        activity_rate = 0.08
    else:
        activity_rate = 0.12
    
    base_volume = followers * activity_rate
    
    logger.info(f"Generating Twitter volume for {symbol}: "
                f"{followers:,} followers × {activity_rate:.1%} = {base_volume:,.0f}/day base")
    
    # 趋势（followers 缓慢增长）
    trend = np.linspace(base_volume * 0.85, base_volume * 1.15, len(date_range))
    
    # 随机日波动 (±25%)
    daily_noise = np.random.normal(0, base_volume * 0.25, len(date_range))
    
    # 周期性（周末 -30%）
    weekly_pattern = np.array([1.0 if d.weekday() < 5 else 0.7 for d in date_range])
    
    # 突发事件（约每 1.5 月一次）
    num_days = len(date_range)
    num_spikes = max(2, int(num_days / 45))
    spike_indices = np.random.choice(num_days, min(num_spikes, num_days), replace=False)
    spike_multiplier = np.ones(num_days)
    spike_multiplier[spike_indices] = np.random.uniform(2.5, 5.0, len(spike_indices))
    
    # 合成
    tweet_counts = (trend + daily_noise) * weekly_pattern * spike_multiplier
    tweet_counts = np.maximum(tweet_counts, 0).astype(int)
    
    df = pd.DataFrame({
        'datetime': date_range,
        'tweet_count': tweet_counts
    })
    
    return df


def _generate_fallback_volume(
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp
) -> pd.DataFrame:
    """
    方法 C：高质量 mock 数据（兜底方案）
    
    基于代币知名度的默认基础量
    """
    default_base_volumes = {
        'BTC': 300000,
        'ETH': 180000,
        'BNB': 90000,
        'SOL': 120000,
        'ADA': 60000,
        'XRP': 75000,
        'DOGE': 150000,
        'DOT': 50000,
        'MATIC': 45000,
        'LINK': 40000,
        'UNI': 35000,
        'LTC': 30000,
        'AVAX': 55000,
        'ATOM': 35000,
        'XMR': 20000,
        'ZEC': 15000,
    }
    
    base_volume = default_base_volumes.get(symbol, 25000)
    
    logger.info(f"Using fallback Twitter volume for {symbol}: {base_volume:,}/day base")
    
    date_range = pd.date_range(start=start, end=end, freq='D', tz='UTC')
    
    trend = np.linspace(base_volume * 0.8, base_volume * 1.2, len(date_range))
    daily_noise = np.random.normal(0, base_volume * 0.2, len(date_range))
    weekly_pattern = np.array([1.0 if d.weekday() < 5 else 0.7 for d in date_range])
    
    num_days = len(date_range)
    num_spikes = max(2, int(num_days / 60))
    spike_indices = np.random.choice(num_days, min(num_spikes, num_days), replace=False)
    spike_multiplier = np.ones(num_days)
    spike_multiplier[spike_indices] = np.random.uniform(2.0, 4.0, len(spike_indices))
    
    tweet_counts = (trend + daily_noise) * weekly_pattern * spike_multiplier
    tweet_counts = np.maximum(tweet_counts, 0).astype(int)
    
    df = pd.DataFrame({
        'datetime': date_range,
        'tweet_count': tweet_counts
    })
    
    return df


def get_twitter_volume_series(
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    granularity: str = "day",
) -> pd.DataFrame:
    """
    获取 Twitter 讨论量数据（智能降级策略）
    
    获取策略（与 Google Trends 保持一致）：
    1. 新代币/首次获取：按价格日线范围获取完整历史数据
    2. 增量更新：只填补缺失日期，如果缓存已有今天/昨天的数据就 SKIP API
    
    尝试顺序：
    1. 数据库缓存
    2. Twitter API（如果配置了 Bearer Token）
    3. CoinGecko followers 数据 + 智能估算
    4. 高质量 mock 数据（兜底）
    """
    start = _normalize_datetime(start)
    end = _normalize_datetime(end)
    today = _normalize_datetime(pd.Timestamp.now(tz="UTC"))
    yesterday = today - pd.Timedelta(days=1)
    cfg = get_symbol_attention_config(symbol)

    db_rows = pd.DataFrame()
    db_handle = None
    
    # Always try to get DB handle
    try:
        db_handle = get_db()
    except Exception as exc:
        logger.warning("Failed to init DB handle for twitter volume: %s", exc)
        db_handle = None

    if db_handle:
        try:
            db_rows = db_handle.get_twitter_volume(symbol, start, end)
            if not db_rows.empty:
                # Rename 'value' to 'tweet_count' to match internal logic
                db_rows = db_rows.rename(columns={'value': 'tweet_count'})
                db_rows["datetime"] = pd.to_datetime(db_rows["datetime"], utc=True).dt.normalize()
        except Exception as exc:
            logger.warning("Failed to load Twitter Volume rows from DB for %s: %s", symbol, exc)

    fetched = pd.DataFrame()
    
    if db_rows.empty:
        # ========== 场景1：新代币，首次全量获取 ==========
        logger.info(
            "Twitter volume: no cache for %s, fetching full history %s → %s",
            symbol, start.date(), end.date()
        )
        fetched = _fetch_twitter_data(symbol, cfg, start, end, granularity)
        
    else:
        # ========== 场景2：已有缓存，判断是否需要增量更新 ==========
        latest_cached = db_rows["datetime"].max()
        
        if latest_cached >= yesterday:
            # 缓存足够新鲜（昨天或今天已有数据），SKIP API 调用
            logger.debug(
                "Twitter volume cache is fresh for %s (latest: %s), skipping fetch",
                symbol, latest_cached.date()
            )
        else:
            # 缓存过时，增量获取：从 (latest_cached + 1天) 到 today
            fetch_start = latest_cached + pd.Timedelta(days=1)
            fetch_end = today
            
            if fetch_start <= fetch_end:
                logger.info(
                    "Twitter volume: incremental fetch for %s, %s → %s",
                    symbol, fetch_start.date(), fetch_end.date()
                )
                fetched = _fetch_twitter_data(symbol, cfg, fetch_start, fetch_end, granularity)
    
    # 保存新获取的数据到数据库
    if not fetched.empty and db_handle:
        try:
            db_handle.save_twitter_volume(symbol, fetched.to_dict("records"))
            logger.info("Twitter volume: saved %d new records for %s", len(fetched), symbol)
        except Exception as exc:
            logger.warning("Failed to persist Twitter Volume rows for %s: %s", symbol, exc)
    
    # Merge fetched data with existing DB data (if any)
    dfs_to_merge = [df for df in (db_rows, fetched) if not df.empty]
    if not dfs_to_merge:
        return pd.DataFrame()
    
    merged = pd.concat(dfs_to_merge, ignore_index=True)
    merged = merged.drop_duplicates(subset=["datetime"], keep="last").sort_values("datetime")

    mask = (merged["datetime"] >= start) & (merged["datetime"] <= end)
    return merged.loc[mask].copy()


def _fetch_twitter_data(
    symbol: str,
    cfg,
    start: pd.Timestamp,
    end: pd.Timestamp,
    granularity: str = "day",
) -> pd.DataFrame:
    """
    实际获取 Twitter 数据的内部函数
    
    策略：
    1. 尝试 Twitter API（如果配置了 Bearer Token）
    2. 如果 API 不可用，返回空 DataFrame（特征值计算会将其视为 0）
    
    注意：不再使用 mock 数据，避免误导分析结果
    """
    # 方法 A：尝试 Twitter API
    fetched = _request_counts(cfg.twitter_query, start, end + pd.Timedelta(days=1), granularity)
    
    if fetched.empty:
        logger.info(f"Twitter API not available for {symbol}, returning empty data (will be treated as 0)")
        # 不再生成 mock 数据，返回空 DataFrame
        # 特征值计算模块会正确处理空数据，将 twitter_volume 设为 0
        return pd.DataFrame()
    else:
        logger.info(f"Successfully fetched Twitter data via API for {symbol}")
    
    return fetched

