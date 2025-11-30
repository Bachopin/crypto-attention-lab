"""
Pure calculation logic for attention features.
Separated from I/O to enable easier testing and better architecture.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.config.attention_channels import (
    COMPOSITE_ATTENTION_WEIGHTS,
    COMPOSITE_SPIKE_QUANTILE,
    get_symbol_attention_config,
)
from src.features.news_features import (
    effective_source_weight,
    extract_tags,
    relevance_flag,
    sentiment_score,
)
from src.features.node_factor_utils import get_node_weight_lookup
from src.utils.math_utils import compute_rolling_zscore, safe_pct_change

logger = logging.getLogger(__name__)

ROLLING_WINDOW_DAYS = 30
# 4H 模式下每天有 6 个周期
PERIODS_PER_DAY_4H = 6


def _get_rolling_window(freq: str) -> int:
    """
    根据频率返回合适的 rolling window 周期数。
    """
    if freq == '4H' or freq == '4h':
        return ROLLING_WINDOW_DAYS * PERIODS_PER_DAY_4H
    return ROLLING_WINDOW_DAYS


def _get_change_periods(freq: str, days: int) -> int:
    """
    根据频率返回变化率计算的周期数。
    """
    if freq == '4H' or freq == '4h':
        return days * PERIODS_PER_DAY_4H
    return days


def _expand_daily_to_4h(daily_df: pd.DataFrame, value_col: str, target_datetime_series: pd.Series) -> pd.Series:
    """
    将日级数据扩展填充到 4H 桶。
    """
    if daily_df.empty:
        return pd.Series(0.0, index=target_datetime_series.index)
    
    # 确保 datetime 列为 DatetimeIndex 且 UTC
    df = daily_df.copy()
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df['date'] = df['datetime'].dt.normalize()
    else:
        # 假设索引是日期，或者有 date 列
        if 'date' in df.columns:
             df['date'] = pd.to_datetime(df['date'], utc=True)
        else:
             # 尝试使用索引
             df['date'] = pd.to_datetime(df.index, utc=True).normalize()

    df = df.drop_duplicates(subset=['date'], keep='last')
    df = df.set_index('date')[value_col]
    
    # 将目标 4H 时间戳映射到日期
    target_dates = pd.to_datetime(target_datetime_series).dt.normalize()
    
    # 按日期匹配填充
    result = target_dates.map(lambda d: df.get(d, 0.0))
    
    return result.fillna(0.0)


def _default_node_id(row: pd.Series) -> str:
    platform = (row.get('platform') or 'news').lower()
    node = row.get('node') or row.get('source') or 'unknown'
    return f"{platform}:{node}"


def calculate_composite_attention(
    symbol: str,
    price_df: pd.DataFrame,
    news_df: Optional[pd.DataFrame] = None,
    google_trends_df: Optional[pd.DataFrame] = None,
    twitter_volume_df: Optional[pd.DataFrame] = None,
    freq: str = 'D'
) -> Optional[pd.DataFrame]:
    """
    Pure function to calculate composite attention features.
    
    Args:
        symbol: Symbol name (e.g., 'ZEC')
        price_df: DataFrame with price data (must have 'datetime' or 'timestamp')
        news_df: Optional DataFrame with news data
        google_trends_df: Optional DataFrame with Google Trends data
        twitter_volume_df: Optional DataFrame with Twitter volume data
        freq: Frequency ('D' or '4H')
        
    Returns:
        DataFrame with calculated features, or None if inputs are invalid.
    """
    freq = freq.upper()
    if freq not in ('D', '4H'):
        logger.warning("Unsupported freq '%s', falling back to 'D'", freq)
        freq = 'D'
    
    resample_freq = '4h' if freq == '4H' else freq

    # 1. Prepare Date Index from Price Data
    if price_df is None or price_df.empty:
        logger.error(f"No price data available for {symbol}")
        return None

    df_price = price_df.copy()
    if 'timestamp' in df_price.columns:
        df_price['datetime'] = pd.to_datetime(df_price['timestamp'], unit='ms', utc=True)
    elif 'date' not in df_price.columns and 'datetime' not in df_price.columns:
        logger.error(f"Price data for {symbol} has no datetime column")
        return None

    date_col = 'datetime' if 'datetime' in df_price.columns else 'date'
    date_range = pd.to_datetime(df_price[date_col], utc=True)
    
    # Create the target time index
    date_index = pd.date_range(
        start=date_range.min(),
        end=date_range.max(),
        freq='D' if freq == 'D' else '4H',
        tz='UTC'
    )

    # 2. Process News Data
    has_news = False
    if news_df is not None and not news_df.empty and 'datetime' in news_df.columns:
        news_df = news_df.copy()
        news_df['datetime'] = pd.to_datetime(news_df['datetime'], utc=True, errors='coerce')
        news_df = news_df.dropna(subset=['datetime'])
        if not news_df.empty:
            has_news = True

    if not has_news:
        grouped = pd.DataFrame({
            'datetime': date_index,
            'news_count': 0,
            'weighted_attention': 0.0,
            'bullish_attention': 0.0,
            'bearish_attention': 0.0,
        })
        rolling_window = _get_rolling_window(freq)
    else:
        cfg = get_symbol_attention_config(symbol)
        node_lookup = get_node_weight_lookup(symbol)

        news_df['language'] = news_df.get('language').fillna(cfg.default_language)
        news_df['platform'] = news_df.get('platform').fillna('news')
        news_df['node'] = news_df.get('node').fillna(news_df.get('source'))
        news_df['node_id'] = news_df.get('node_id')
        
        # Fill missing node_id
        missing_node_mask = news_df['node_id'].isna() | (news_df['node_id'] == '')
        if missing_node_mask.any():
            news_df.loc[missing_node_mask, 'node_id'] = news_df.loc[missing_node_mask].apply(_default_node_id, axis=1)

        # Calculate scores if missing
        if 'sentiment_score' not in news_df.columns:
            news_df['sentiment_score'] = news_df['title'].apply(lambda t: sentiment_score(str(t)))
        if 'relevance' not in news_df.columns:
            news_df['relevance'] = news_df['title'].apply(lambda t: relevance_flag(str(t), symbol=symbol))
        if 'tags' not in news_df.columns:
            news_df['tags'] = news_df['title'].apply(lambda t: ','.join(extract_tags(str(t))))

        news_df['source_weight'] = news_df.apply(
            lambda row: effective_source_weight(
                row.get('source', 'Unknown'),
                language=row.get('language'),
                node_id=row.get('node_id'),
                node_weight_lookup=node_lookup,
            ),
            axis=1,
        )

        rel_weight = news_df['relevance'].map({'direct': 1.0, 'related': 0.5}).fillna(0.5)
        news_df['weighted_score'] = news_df['source_weight'] * rel_weight
        news_df['bullish_component'] = (news_df['sentiment_score'].clip(lower=0)) * news_df['weighted_score']
        news_df['bearish_component'] = (-news_df['sentiment_score'].clip(upper=0)) * news_df['weighted_score']

        # Aggregate to target frequency
        grouped = news_df.set_index('datetime').resample(resample_freq).agg({
            'title': 'count',
            'weighted_score': 'sum',
            'bullish_component': 'sum',
            'bearish_component': 'sum',
        }).rename(columns={
            'title': 'news_count',
            'weighted_score': 'weighted_attention',
            'bullish_component': 'bullish_attention',
            'bearish_component': 'bearish_attention',
        })

        grouped = grouped.fillna(0).reset_index()

        # Align with full date index
        base = pd.DataFrame({'datetime': date_index})
        grouped = base.merge(grouped, on='datetime', how='left')
        grouped[['news_count','weighted_attention','bullish_attention','bearish_attention']] = (
            grouped[['news_count','weighted_attention','bullish_attention','bearish_attention']].fillna(0)
        )

        rolling_window = _get_rolling_window(freq)
        
        mn = grouped['news_count'].min()
        mx = grouped['news_count'].max()
        grouped['attention_score'] = 0.0 if mx == mn else (grouped['news_count'] - mn) / (mx - mn) * 100.0
        grouped['news_channel_score'] = compute_rolling_zscore(grouped['weighted_attention'], window=rolling_window)

    # 3. Process Google Trends
    if google_trends_df is not None and not google_trends_df.empty:
        gt = google_trends_df.copy()
        # Ensure standard column name
        if 'value' in gt.columns:
            gt = gt.rename(columns={'value': 'google_trend_value'})
        
        if freq == '4H':
            grouped['google_trend_value'] = _expand_daily_to_4h(
                gt, 'google_trend_value', grouped['datetime']
            )
        else:
            # Ensure datetime type for merge
            if 'datetime' in gt.columns:
                gt['datetime'] = pd.to_datetime(gt['datetime'], utc=True)
                grouped = grouped.merge(gt[['datetime', 'google_trend_value']], on='datetime', how='left')
            else:
                # Fallback if no datetime col (unlikely if coming from fetcher)
                pass
    
    grouped['google_trend_value'] = grouped.get('google_trend_value', pd.Series(index=grouped.index)).fillna(0.0)
    grouped['google_trend_zscore'] = compute_rolling_zscore(grouped['google_trend_value'], window=rolling_window)
    grouped['google_trend_change_7d'] = safe_pct_change(grouped['google_trend_value'], _get_change_periods(freq, 7))
    grouped['google_trend_change_30d'] = safe_pct_change(grouped['google_trend_value'], _get_change_periods(freq, 30))

    # 4. Process Twitter Volume
    if twitter_volume_df is not None and not twitter_volume_df.empty:
        tw = twitter_volume_df.copy()
        if 'tweet_count' in tw.columns:
            tw = tw.rename(columns={'tweet_count': 'twitter_volume'})
            
        if freq == '4H':
            grouped['twitter_volume'] = _expand_daily_to_4h(
                tw, 'twitter_volume', grouped['datetime']
            )
        else:
            if 'datetime' in tw.columns:
                tw['datetime'] = pd.to_datetime(tw['datetime'], utc=True)
                grouped = grouped.merge(tw[['datetime', 'twitter_volume']], on='datetime', how='left')

    grouped['twitter_volume'] = grouped.get('twitter_volume', pd.Series(index=grouped.index)).fillna(0.0)
    grouped['twitter_volume_zscore'] = compute_rolling_zscore(grouped['twitter_volume'], window=rolling_window)
    grouped['twitter_volume_change_7d'] = safe_pct_change(grouped['twitter_volume'], _get_change_periods(freq, 7))

    # 5. Composite Attention
    components = {
        'news': grouped['news_channel_score'].fillna(0.0),
        'google_trends': grouped['google_trend_zscore'].fillna(0.0),
        'twitter': grouped['twitter_volume_zscore'].fillna(0.0),
    }
    composite = sum(COMPOSITE_ATTENTION_WEIGHTS.get(k, 0.0) * v for k, v in components.items())
    grouped['composite_attention_score'] = composite
    grouped['composite_attention_zscore'] = compute_rolling_zscore(grouped['composite_attention_score'], window=rolling_window)

    quantile = grouped['composite_attention_score'].rolling(
        window=rolling_window,
        min_periods=max(10, rolling_window // 2),
    ).quantile(COMPOSITE_SPIKE_QUANTILE)
    
    grouped['composite_attention_spike_flag'] = (
        grouped['composite_attention_score'] >= quantile
    ).astype(int).where(~quantile.isna(), 0)
    grouped['composite_attention_spike_flag'] = grouped['composite_attention_spike_flag'].fillna(0).astype(int)

    # 6. Event Intensity (Legacy)
    if has_news:
        daily = news_df.copy()
        daily['date'] = daily['datetime'].dt.floor(resample_freq)

        def compute_intensity(day_df: pd.DataFrame) -> int:
            has_high_source = (day_df['source_weight'] >= 0.9).any()
            strong_sent = (day_df['sentiment_score'].abs() >= 0.6).any()
            has_tag = day_df['tags'].astype(str).str.len().gt(0).any()
            return int(has_high_source and strong_sent and has_tag)

        intensity = (daily.groupby('date', as_index=False)
                     .apply(lambda x: pd.Series({'event_intensity': compute_intensity(x)}), include_groups=False)
                     )
        grouped = grouped.merge(intensity, left_on='datetime', right_on='date', how='left').drop(columns=['date'])
        grouped['event_intensity'] = grouped['event_intensity'].fillna(0).astype(int)
    else:
        grouped['event_intensity'] = 0

    # 7. Final Cleanup
    out_columns = [
        'datetime',
        'attention_score',
        'news_count',
        'weighted_attention',
        'bullish_attention',
        'bearish_attention',
        'event_intensity',
        'news_channel_score',
        'google_trend_value',
        'google_trend_zscore',
        'google_trend_change_7d',
        'google_trend_change_30d',
        'twitter_volume',
        'twitter_volume_zscore',
        'twitter_volume_change_7d',
        'composite_attention_score',
        'composite_attention_zscore',
        'composite_attention_spike_flag',
    ]

    out = grouped[out_columns].copy()
    out['timeframe'] = freq
    
    return out
