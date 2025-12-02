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
    force_refresh: bool = False,
) -> pd.DataFrame:
    """增量获取 Twitter 讨论量（使用 attention_features 作为缓存来源并支持降级策略）

    策略：
    1. 非 force_refresh 情况下，先查询 attention_features 已有 twitter_volume 范围
       - 缓存为空：抓取 start~end
       - 缓存已覆盖 end：直接返回缓存
       - 否则：仅抓取缺失区间 (latest_cached+1) ~ end
    2. 缺失区间获取顺序：仅 Twitter API；若不可用则返回空
    3. 不再使用旧独立 twitter_volumes 表

    返回格式：DataFrame[datetime, tweet_count]
    """
    symbol = symbol.upper()
    start = _normalize_datetime(start)
    end = _normalize_datetime(end)
    cfg = get_symbol_attention_config(symbol)

    existing_df = pd.DataFrame()
    if USE_DATABASE and not force_refresh:
        try:
            db = get_db()
            existing_df = db.get_attention_features(symbol, start=start, end=end, timeframe='D')
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("Failed to load existing attention_features for %s: %s", symbol, e)
            existing_df = pd.DataFrame()

    if not existing_df.empty and 'datetime' in existing_df.columns:
        existing_df['datetime'] = pd.to_datetime(existing_df['datetime'], utc=True).dt.normalize()
        existing_df = existing_df.drop_duplicates(subset=['datetime'], keep='last').sort_values('datetime')

    need_fetch = True
    fetch_start = start
    if force_refresh:
        need_fetch = True
    elif existing_df.empty:
        need_fetch = True
    else:
        latest_cached = existing_df['datetime'].max()
        if latest_cached >= end:
            need_fetch = False
        else:
            fetch_start = latest_cached + pd.Timedelta(days=1)
            if fetch_start > end:
                need_fetch = False

    fetched_df = pd.DataFrame()
    if need_fetch:
        # 仅对缺失区间执行 API 获取；API 不可用则返回空
        interval_start = fetch_start
        interval_end = end
        api_df = _request_counts(cfg.twitter_query, interval_start, interval_end + pd.Timedelta(days=1), granularity)
        if not api_df.empty:
            fetched_df = api_df
            logger.info("Twitter API fetched %d rows for %s", len(fetched_df), symbol)
        else:
            fetched_df = pd.DataFrame()
            logger.info("Twitter API not available; twitter_volume will be treated as 0 for %s", symbol)

        if not fetched_df.empty:
            fetched_df['datetime'] = pd.to_datetime(fetched_df['datetime'], utc=True).dt.normalize()
            fetched_df = fetched_df.drop_duplicates(subset=['datetime'], keep='last').sort_values('datetime')

    # 合并已有与新抓取数据
    if existing_df.empty:
        combined = fetched_df
        if 'tweet_count' not in combined.columns and 'twitter_volume' in combined.columns:
            combined = combined.rename(columns={'twitter_volume': 'tweet_count'})
    elif fetched_df.empty:
        combined = existing_df[['datetime', 'twitter_volume']].rename(columns={'twitter_volume': 'tweet_count'})
    else:
        ex = existing_df[['datetime', 'twitter_volume']].rename(columns={'twitter_volume': 'tweet_count'})
        new = fetched_df[['datetime', 'tweet_count']] if 'tweet_count' in fetched_df.columns else fetched_df[['datetime']].assign(tweet_count=fetched_df.get('tweet_count', 0))
        combined = pd.concat([ex, new], ignore_index=True)
        combined = combined.drop_duplicates(subset=['datetime'], keep='last').sort_values('datetime')

    if combined.empty:
        return pd.DataFrame(columns=['datetime', 'tweet_count'])

    mask = (combined['datetime'] >= start) & (combined['datetime'] <= end)
    out = combined.loc[mask].copy()
    return out[['datetime', 'tweet_count']].reset_index(drop=True)


def _fetch_twitter_data(*args, **kwargs):  # 保留占位避免外部误用旧接口
    logger.debug("_fetch_twitter_data legacy interface is deprecated; logic moved into get_twitter_volume_series")
    return pd.DataFrame()

