from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

from src.config.attention_channels import (
    COMPOSITE_ATTENTION_WEIGHTS,
    COMPOSITE_SPIKE_QUANTILE,
    get_symbol_attention_config,
)
from src.data.db_storage import USE_DATABASE, get_db
from src.data.google_trends_fetcher import get_google_trends_series
from src.data.twitter_attention_fetcher import get_twitter_volume_series
from src.features.news_features import (
    effective_source_weight,
    extract_tags,
    relevance_flag,
    sentiment_score,
)
from src.features.node_factor_utils import get_node_weight_lookup

logger = logging.getLogger(__name__)

ROLLING_WINDOW_DAYS = 30


def _rolling_zscore(series: pd.Series, window: int = ROLLING_WINDOW_DAYS) -> pd.Series:
    rolling = series.rolling(window=window, min_periods=max(5, window // 2))
    mean = rolling.mean()
    std = rolling.std(ddof=0)
    std = std.replace(0, np.nan)
    z = (series - mean) / std
    return z.fillna(0.0)


def _safe_pct_change(series: pd.Series, periods: int) -> pd.Series:
    prev = series.shift(periods)
    change = (series - prev) / prev.replace(0, np.nan)
    return change.replace([np.nan, np.inf, -np.inf], 0.0).fillna(0.0)


def _default_node_id(row: pd.Series) -> str:
    platform = (row.get('platform') or 'news').lower()
    node = row.get('node') or row.get('source') or 'unknown'
    return f"{platform}:{node}"


def process_attention_features(symbol: str = 'ZEC', freq: str = 'D'):
    """Build the multi-channel attention feature set for a given symbol."""

    from src.data.db_storage import load_news_data

    logger.info("Processing composite attention features for %s", symbol)

    start_date = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=180)
    news_df = load_news_data(symbol, start=start_date)

    if news_df.empty or 'datetime' not in news_df.columns:
        logger.warning("No usable news data for %s", symbol)
        return None

    news_df['datetime'] = pd.to_datetime(news_df['datetime'], utc=True, errors='coerce')
    news_df = news_df.dropna(subset=['datetime'])
    if news_df.empty:
        logger.warning("News dataframe became empty after datetime cleanup for %s", symbol)
        return None

    cfg = get_symbol_attention_config(symbol)
    node_lookup = get_node_weight_lookup(symbol)

    news_df['language'] = news_df.get('language').fillna(cfg.default_language)
    news_df['platform'] = news_df.get('platform').fillna('news')
    news_df['node'] = news_df.get('node').fillna(news_df.get('source'))
    news_df['node_id'] = news_df.get('node_id')
    missing_node_mask = news_df['node_id'].isna() | (news_df['node_id'] == '')
    news_df.loc[missing_node_mask, 'node_id'] = news_df.loc[missing_node_mask].apply(_default_node_id, axis=1)

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

    grouped = news_df.set_index('datetime').resample(freq).agg({
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

    mn = grouped['news_count'].min()
    mx = grouped['news_count'].max()
    grouped['attention_score'] = 0.0 if mx == mn else (grouped['news_count'] - mn) / (mx - mn) * 100.0

    grouped['news_channel_score'] = _rolling_zscore(grouped['weighted_attention'])

    start_range = grouped['datetime'].min()
    end_range = grouped['datetime'].max()

    # Google Trends channel
    gt = get_google_trends_series(symbol, start_range - pd.Timedelta(days=7), end_range)
    if not gt.empty:
        gt = gt.rename(columns={'value': 'google_trend_value'})
        grouped = grouped.merge(gt, on='datetime', how='left')
    grouped['google_trend_value'] = grouped.get('google_trend_value', pd.Series(index=grouped.index)).fillna(0.0)
    grouped['google_trend_zscore'] = _rolling_zscore(grouped['google_trend_value'])
    grouped['google_trend_change_7d'] = _safe_pct_change(grouped['google_trend_value'], 7)
    grouped['google_trend_change_30d'] = _safe_pct_change(grouped['google_trend_value'], 30)

    # Twitter volume channel
    tw = get_twitter_volume_series(symbol, start_range - pd.Timedelta(days=7), end_range)
    if not tw.empty:
        tw = tw.rename(columns={'tweet_count': 'twitter_volume'})
        grouped = grouped.merge(tw, on='datetime', how='left')
    grouped['twitter_volume'] = grouped.get('twitter_volume', pd.Series(index=grouped.index)).fillna(0.0)
    grouped['twitter_volume_zscore'] = _rolling_zscore(grouped['twitter_volume'])
    grouped['twitter_volume_change_7d'] = _safe_pct_change(grouped['twitter_volume'], 7)

    # Composite attention
    components = {
        'news': grouped['news_channel_score'].fillna(0.0),
        'google_trends': grouped['google_trend_zscore'].fillna(0.0),
        'twitter': grouped['twitter_volume_zscore'].fillna(0.0),
    }
    composite = sum(COMPOSITE_ATTENTION_WEIGHTS.get(k, 0.0) * v for k, v in components.items())
    grouped['composite_attention_score'] = composite
    grouped['composite_attention_zscore'] = _rolling_zscore(grouped['composite_attention_score'])

    quantile = grouped['composite_attention_score'].rolling(
        window=ROLLING_WINDOW_DAYS,
        min_periods=max(10, ROLLING_WINDOW_DAYS // 2),
    ).quantile(COMPOSITE_SPIKE_QUANTILE)
    grouped['composite_attention_spike_flag'] = (
        grouped['composite_attention_score'] >= quantile
    ).astype(int).where(~quantile.isna(), 0)
    grouped['composite_attention_spike_flag'] = grouped['composite_attention_spike_flag'].fillna(0).astype(int)

    # Legacy event intensity logic
    daily = news_df.copy()
    daily['date'] = daily['datetime'].dt.floor(freq)

    def compute_intensity(day_df: pd.DataFrame) -> int:
        has_high_source = (day_df['source_weight'] >= 0.9).any()
        strong_sent = (day_df['sentiment_score'].abs() >= 0.6).any()
        has_tag = day_df['tags'].astype(str).str.len().gt(0).any()
        return int(has_high_source and strong_sent and has_tag)

    if not daily.empty:
        intensity = daily.groupby('date').apply(compute_intensity).rename('event_intensity').reset_index()
        grouped = grouped.merge(intensity, left_on='datetime', right_on='date', how='left').drop(columns=['date'])
        grouped['event_intensity'] = grouped['event_intensity'].fillna(0).astype(int)
    else:
        grouped['event_intensity'] = 0

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

    out = grouped[out_columns]

    if USE_DATABASE:
        try:
            db = get_db()
            db.save_attention_features(symbol, out.to_dict('records'))
            logger.info("Saved %d attention rows for %s", len(out), symbol)
        except Exception as exc:
            logger.error("Failed to persist attention features: %s", exc)
            return None

    return out


if __name__ == "__main__":
    process_attention_features(symbol='ZEC')
