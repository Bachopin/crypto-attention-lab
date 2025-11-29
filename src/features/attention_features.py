"""
Attention Feature Engineering Module

本模块实现多通道注意力特征聚合，支持日级（freq='D'）和 4 小时级（freq='4H'）两种频率。

4H 支持说明：
- 新闻通道：直接按 4H 桶聚合，新闻时间戳精确到小时，能够正确分配到 4H 窗口
- Google Trends 通道：目前仅有日级数据，采用「日内均匀填充」近似方案，
  即同一天的所有 4H 桶填充相同的日级值。未来可接入小时级 Trends API 改进。
- Twitter 通道：同 Google Trends，日级数据均匀填充到 4H 桶。

注意事项：
- 4H 模式下 rolling window 单位从「天」变为「4H 周期数」，
  默认 30 天 = 180 个 4H 周期
- z-score 和变化率计算逻辑保持一致，仅窗口大小随频率调整
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

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
# 4H 模式下每天有 6 个周期
PERIODS_PER_DAY_4H = 6


def _get_rolling_window(freq: str) -> int:
    """
    根据频率返回合适的 rolling window 周期数。
    
    对于日级（D），直接使用 ROLLING_WINDOW_DAYS。
    对于 4H 级，将天数转换为 4H 周期数（每天 6 个周期）。
    """
    if freq == '4H' or freq == '4h':
        return ROLLING_WINDOW_DAYS * PERIODS_PER_DAY_4H  # 30天 = 180个4H周期
    return ROLLING_WINDOW_DAYS


def _get_change_periods(freq: str, days: int) -> int:
    """
    根据频率返回变化率计算的周期数。
    
    例如 7 天变化率：
    - 日级：7 个周期
    - 4H 级：7 * 6 = 42 个周期
    """
    if freq == '4H' or freq == '4h':
        return days * PERIODS_PER_DAY_4H
    return days


def _expand_daily_to_4h(daily_df: pd.DataFrame, value_col: str, target_datetime_series: pd.Series) -> pd.Series:
    """
    将日级数据扩展填充到 4H 桶。
    
    采用「日内均匀填充」近似方案：同一天的所有 4H 桶填充相同的日级值。
    这是当前 Google Trends / Twitter 数据仅有日级粒度时的折中方案。
    
    Parameters
    ----------
    daily_df : pd.DataFrame
        包含 'datetime' 和 value_col 的日级数据
    value_col : str
        值列名
    target_datetime_series : pd.Series
        目标 4H 时间戳序列（grouped DataFrame 的 datetime 列）
    
    Returns
    -------
    pd.Series
        与 target_datetime_series 对齐的值序列，缺失值填充为 0
    
    Notes
    -----
    近似假设：日内 6 个 4H 桶的值相同，等于当日的日级值。
    未来改进方向：接入小时级 API 或使用插值方法。
    """
    if daily_df.empty:
        return pd.Series(0.0, index=target_datetime_series.index)
    
    # 确保 datetime 列为 DatetimeIndex 且 UTC
    df = daily_df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    df['date'] = df['datetime'].dt.normalize()  # 提取日期部分
    df = df.drop_duplicates(subset=['date'], keep='last')
    df = df.set_index('date')[value_col]
    
    # 将目标 4H 时间戳映射到日期
    target_dates = pd.to_datetime(target_datetime_series).dt.normalize()
    
    # 按日期匹配填充
    result = target_dates.map(lambda d: df.get(d, 0.0))
    
    return result.fillna(0.0)


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


def process_attention_features(
    symbol: str = 'ZEC',
    freq: str = 'D',
    save_to_db: bool = True,
) -> Optional[pd.DataFrame]:
    """
    Build the multi-channel attention feature set for a given symbol.
    
    Parameters
    ----------
    symbol : str
        加密货币符号，如 'ZEC', 'BTC', 'ETH'
    freq : str
        时间频率，支持 'D'（日级）和 '4H'（4小时级）
    save_to_db : bool
        是否保存到数据库。对于 4H 模式，由于表结构变更风险，
        默认仍然尝试保存，但如果表不支持 timeframe 字段会降级为仅返回 DataFrame
    
    Returns
    -------
    pd.DataFrame or None
        包含多通道注意力特征的 DataFrame，失败时返回 None
    
    Notes
    -----
    4H 模式说明：
    - 新闻数据按 4H 窗口精确聚合
    - Google Trends / Twitter 数据仅有日级，采用「日内均匀填充」近似：
      同一天的所有 4H 桶填充相同的日级值
    - rolling window 自动调整为等效天数（30天 = 180个4H周期）
    - 变化率周期数同步调整（7天变化 = 42个4H周期）
    """

    from src.data.db_storage import load_news_data

    freq = freq.upper()
    if freq not in ('D', '4H'):
        logger.warning("Unsupported freq '%s', falling back to 'D'", freq)
        freq = 'D'
    
    # pandas resample 需要使用小写的 'h'（新版 pandas 弃用大写 'H'）
    resample_freq = '4h' if freq == '4H' else freq
    
    logger.info("Processing composite attention features for %s (freq=%s)", symbol, freq)

    start_date = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=180)
    news_df = load_news_data(symbol, start=start_date)

    has_news = not news_df.empty and 'datetime' in news_df.columns
    
    if has_news:
        news_df['datetime'] = pd.to_datetime(news_df['datetime'], utc=True, errors='coerce')
        news_df = news_df.dropna(subset=['datetime'])
        has_news = not news_df.empty
    
    if not has_news:
        logger.warning("No usable news data for %s; will compute attention from Google Trends + Twitter only", symbol)
        # 创建空的时间序列 DataFrame，基于价格数据的日期范围
        from src.data.db_storage import load_price_data
        price_data = load_price_data(symbol, timeframe='1d')
        if isinstance(price_data, tuple):
            price_df, _ = price_data
        else:
            price_df = price_data
        
        if price_df is None or price_df.empty:
            logger.error(f"No price data available for {symbol}, cannot generate attention features")
            return None
        
        # 使用价格数据的日期范围
        if 'timestamp' in price_df.columns:
            price_df['datetime'] = pd.to_datetime(price_df['timestamp'], unit='ms', utc=True)
        elif 'date' not in price_df.columns and 'datetime' not in price_df.columns:
            logger.error(f"Price data for {symbol} has no datetime column")
            return None
        
        date_col = 'datetime' if 'datetime' in price_df.columns else 'date'
        date_range = pd.to_datetime(price_df[date_col], utc=True)
        date_index = pd.date_range(
            start=date_range.min(),
            end=date_range.max(),
            freq='D' if freq == 'D' else '4H',
            tz='UTC'
        )
        
        # 创建空的新闻统计 DataFrame
        grouped = pd.DataFrame({
            'datetime': date_index,
            'news_count': 0,
            'weighted_attention': 0.0,
            'bullish_attention': 0.0,
            'bearish_attention': 0.0,
            'attention_score': 0.0,
            'news_channel_score': 0.0,
        })
        rolling_window = _get_rolling_window(freq)
    else:
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

        mn = grouped['news_count'].min()
        mx = grouped['news_count'].max()
        grouped['attention_score'] = 0.0 if mx == mn else (grouped['news_count'] - mn) / (mx - mn) * 100.0

        # 使用频率相关的 rolling window
        rolling_window = _get_rolling_window(freq)
        grouped['news_channel_score'] = _rolling_zscore(grouped['weighted_attention'], window=rolling_window)

    start_range = grouped['datetime'].min()
    end_range = grouped['datetime'].max()

    # Google Trends channel
    # 注意：Google Trends 目前仅提供日级数据
    gt = get_google_trends_series(symbol, start_range - pd.Timedelta(days=7), end_range)
    if not gt.empty:
        gt = gt.rename(columns={'value': 'google_trend_value'})
        if freq == '4H':
            # 4H 模式：将日级数据填充到 4H 桶（同一天的所有 4H 桶填充相同值）
            # 这是当前的近似方案，未来可改进为插值或接入小时级 API
            grouped['google_trend_value'] = _expand_daily_to_4h(
                gt, 'google_trend_value', grouped['datetime']
            )
            logger.info(
                "Google Trends: expanded daily data to 4H buckets for %s (approximation: same-day fill)",
                symbol,
            )
        else:
            grouped = grouped.merge(gt, on='datetime', how='left')
    else:
        logger.warning(
            "Google Trends channel empty for %s (%s → %s); falling back to zeros",
            symbol,
            (start_range - pd.Timedelta(days=7)).date(),
            end_range.date(),
        )
    grouped['google_trend_value'] = grouped.get('google_trend_value', pd.Series(index=grouped.index)).fillna(0.0)
    grouped['google_trend_zscore'] = _rolling_zscore(grouped['google_trend_value'], window=rolling_window)
    grouped['google_trend_change_7d'] = _safe_pct_change(grouped['google_trend_value'], _get_change_periods(freq, 7))
    grouped['google_trend_change_30d'] = _safe_pct_change(grouped['google_trend_value'], _get_change_periods(freq, 30))

    # Twitter volume channel
    # 注意：Twitter 数据目前仅提供日级粒度
    tw = get_twitter_volume_series(symbol, start_range - pd.Timedelta(days=7), end_range)
    if not tw.empty:
        tw = tw.rename(columns={'tweet_count': 'twitter_volume'})
        if freq == '4H':
            # 4H 模式：将日级数据填充到 4H 桶（同一天的所有 4H 桶填充相同值）
            # 这是当前的近似方案，未来可改进为插值或接入小时级 API
            grouped['twitter_volume'] = _expand_daily_to_4h(
                tw, 'twitter_volume', grouped['datetime']
            )
            logger.info(
                "Twitter volume: expanded daily data to 4H buckets for %s (approximation: same-day fill)",
                symbol,
            )
        else:
            grouped = grouped.merge(tw, on='datetime', how='left')
    grouped['twitter_volume'] = grouped.get('twitter_volume', pd.Series(index=grouped.index)).fillna(0.0)
    grouped['twitter_volume_zscore'] = _rolling_zscore(grouped['twitter_volume'], window=rolling_window)
    grouped['twitter_volume_change_7d'] = _safe_pct_change(grouped['twitter_volume'], _get_change_periods(freq, 7))

    # Composite attention
    components = {
        'news': grouped['news_channel_score'].fillna(0.0),
        'google_trends': grouped['google_trend_zscore'].fillna(0.0),
        'twitter': grouped['twitter_volume_zscore'].fillna(0.0),
    }
    composite = sum(COMPOSITE_ATTENTION_WEIGHTS.get(k, 0.0) * v for k, v in components.items())
    grouped['composite_attention_score'] = composite
    grouped['composite_attention_zscore'] = _rolling_zscore(grouped['composite_attention_score'], window=rolling_window)

    quantile = grouped['composite_attention_score'].rolling(
        window=rolling_window,
        min_periods=max(10, rolling_window // 2),
    ).quantile(COMPOSITE_SPIKE_QUANTILE)
    grouped['composite_attention_spike_flag'] = (
        grouped['composite_attention_score'] >= quantile
    ).astype(int).where(~quantile.isna(), 0)
    grouped['composite_attention_spike_flag'] = grouped['composite_attention_spike_flag'].fillna(0).astype(int)

    # Legacy event intensity logic
    if has_news and not news_df.empty:
        daily = news_df.copy()
        daily['date'] = daily['datetime'].dt.floor(resample_freq)

        def compute_intensity(day_df: pd.DataFrame) -> int:
            has_high_source = (day_df['source_weight'] >= 0.9).any()
            strong_sent = (day_df['sentiment_score'].abs() >= 0.6).any()
            has_tag = day_df['tags'].astype(str).str.len().gt(0).any()
            return int(has_high_source and strong_sent and has_tag)

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

    out = grouped[out_columns].copy()
    
    # 添加 timeframe 标识列，便于后续区分不同频率的数据
    out['timeframe'] = freq

    if USE_DATABASE and save_to_db:
        try:
            db = get_db()
            # 传入 timeframe 参数以区分不同频率的数据
            # 如果 db.save_attention_features 不支持 timeframe，会降级为仅返回 DataFrame
            db.save_attention_features(symbol, out.to_dict('records'), timeframe=freq)
            logger.info("Saved %d attention rows for %s (freq=%s)", len(out), symbol, freq)
        except TypeError as te:
            # 旧版 save_attention_features 可能不支持 timeframe 参数
            logger.warning(
                "save_attention_features does not support timeframe param yet; "
                "4H data returned as DataFrame only. Error: %s", te
            )
            # 降级：不保存到数据库，仅返回 DataFrame
        except Exception as exc:
            logger.error("Failed to persist attention features: %s", exc)
            # 仍然返回 DataFrame 而不是 None，让调用方可以使用数据
            logger.info("Returning DataFrame without DB persistence for %s (freq=%s)", symbol, freq)

    return out


if __name__ == "__main__":
    process_attention_features(symbol='ZEC')
