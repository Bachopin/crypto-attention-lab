"""
State Snapshot Module for Crypto Attention Lab

本模块实现 StateSnapshot 功能，用于构建某个 symbol 在某时刻的状态特征向量。
状态快照整合了价格、波动率和注意力等多维度信息，便于后续进行：
- 相似模式检索（Scenario Engine）
- 情景分析（类似历史模式的价格表现）
- 多因子综合评估

设计理念：
1. 特征规范化：对不同量纲的特征进行 z-score 标准化，避免量级差异影响相似度计算
2. 原始统计保留：raw_stats 字段保留未标准化的原始值，便于前端展示和调试
3. 可扩展性：当前为 rule-based 特征，后续可替换为 ML 模型生成的 embedding
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd

from src.data.db_storage import load_price_data, load_attention_data, load_news_data

logger = logging.getLogger(__name__)


@dataclass
class StateSnapshot:
    """
    状态快照结构，封装某 symbol 在 as_of 时刻的多维特征向量。
    
    Attributes
    ----------
    symbol : str
        加密货币符号，如 'ZEC', 'BTC'
    as_of : datetime
        快照时间点（UTC）
    timeframe : str
        数据时间粒度，'1d' 或 '4h'
    window_days : int
        用于计算滚动统计的窗口天数
    features : Dict[str, float]
        规范化后的数值特征，用于相似度计算
        所有特征均经过 z-score 或等效标准化处理
    raw_stats : Dict[str, Any]
        原始统计值，便于前端展示和调试
        包含未经标准化的价格、volume、attention 等数据
    """
    symbol: str
    as_of: datetime
    timeframe: str
    window_days: int
    features: Dict[str, float] = field(default_factory=dict)
    raw_stats: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """将快照转换为可 JSON 序列化的字典"""
        result = asdict(self)
        # datetime 需要转换为 ISO 字符串
        result['as_of'] = self.as_of.isoformat() if self.as_of else None
        return result


# ========== 辅助函数 ==========

def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全地将值转换为 float，处理 None/NaN/Inf"""
    if value is None:
        return default
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _compute_zscore(value: float, mean: float, std: float) -> float:
    """
    计算 z-score，处理标准差为零的情况
    
    Parameters
    ----------
    value : float
        当前值
    mean : float
        均值
    std : float
        标准差
    
    Returns
    -------
    float
        z-score 值，std 为 0 时返回 0
    """
    if std == 0 or np.isnan(std) or std is None:
        return 0.0
    return (value - mean) / std


def _compute_log_return(prices: pd.Series) -> float:
    """
    计算累计对数收益率
    
    Parameters
    ----------
    prices : pd.Series
        按时间排序的价格序列
    
    Returns
    -------
    float
        累计对数收益率 ln(P_end / P_start)
    """
    if prices.empty or len(prices) < 2:
        return 0.0
    
    start_price = prices.iloc[0]
    end_price = prices.iloc[-1]
    
    if start_price <= 0 or end_price <= 0:
        return 0.0
    
    return float(np.log(end_price / start_price))


def _compute_volatility(prices: pd.Series) -> float:
    """
    计算价格序列的收益率标准差（波动率代理）
    
    Parameters
    ----------
    prices : pd.Series
        按时间排序的价格序列
    
    Returns
    -------
    float
        对数收益率的标准差
    """
    if prices.empty or len(prices) < 3:
        return 0.0
    
    log_returns = np.log(prices / prices.shift(1)).dropna()
    
    if log_returns.empty:
        return 0.0
    
    return float(log_returns.std(ddof=1))


def _compute_slope(series: pd.Series) -> float:
    """
    计算时间序列的线性趋势斜率
    
    使用简单线性回归：y = a + b*x
    返回斜率 b，表示每个时间单位的变化量
    
    Parameters
    ----------
    series : pd.Series
        时间序列数据
    
    Returns
    -------
    float
        线性趋势斜率
    """
    if series.empty or len(series) < 2:
        return 0.0
    
    # 去除 NaN
    clean = series.dropna()
    if len(clean) < 2:
        return 0.0
    
    x = np.arange(len(clean))
    y = clean.values
    
    # 简单线性回归
    try:
        slope, _ = np.polyfit(x, y, 1)
        return float(slope)
    except Exception:
        return 0.0


# ========== 价格/波动特征计算 ==========

def _compute_price_features(
    symbol: str,
    as_of: datetime,
    timeframe: str,
    window_days: int,
    price_df: Optional[pd.DataFrame] = None,
) -> tuple[Dict[str, float], Dict[str, Any]]:
    """
    计算价格和波动率相关特征
    
    Features (规范化):
    - ret_window: 窗口累计对数收益的 z-score（相对于更长历史）
    - vol_window: 窗口波动率的 z-score
    - volume_zscore: 最近 7D 平均成交量相对窗口内均值的 z-score
    
    Raw Stats:
    - close_price: 最新收盘价
    - high_window: 窗口内最高价
    - low_window: 窗口内最低价
    - avg_volume_7d: 最近 7D 平均成交量
    - avg_volume_window: 窗口内平均成交量
    
    Parameters
    ----------
    symbol : str
        币种符号
    as_of : datetime
        截止时间
    timeframe : str
        时间粒度 '1d' 或 '4h'
    window_days : int
        窗口天数
    price_df : pd.DataFrame | None
        预加载的价格数据（可选），若提供则直接从中切片，避免 DB 查询
    
    Returns
    -------
    tuple[Dict[str, float], Dict[str, Any]]
        (features, raw_stats)
    """
    features: Dict[str, float] = {}
    raw_stats: Dict[str, Any] = {}
    
    # 标准化 symbol 格式
    symbol_code = symbol if symbol.endswith('USDT') else f"{symbol}USDT"
    
    # 加载更长的历史数据用于 z-score 计算（2x window）
    lookback_days = window_days * 2 + 7  # 额外 7 天用于 volume_zscore
    start_dt = as_of - pd.Timedelta(days=lookback_days)
    
    if price_df is None:
        df, _ = load_price_data(symbol_code, timeframe, start_dt, as_of)
    else:
        # 从预加载数据中切片
        # 假设 price_df 已经包含所需列且 datetime 为 UTC
        mask = (price_df['datetime'] > start_dt) & (price_df['datetime'] <= as_of)
        df = price_df.loc[mask].copy()
    
    if df.empty or 'close' not in df.columns:
        # logger.warning(f"No price data for {symbol} ({timeframe})")
        return features, raw_stats
    
    # 确保 datetime 列存在且为 UTC
    if 'datetime' in df.columns:
        # 如果是从 DB 加载的，可能需要转换；如果是预加载的，假设已经转换好
        if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
            df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        
        # 确保有时区信息
        if df['datetime'].dt.tz is None:
            df['datetime'] = df['datetime'].dt.tz_localize('UTC')
            
        df = df.sort_values('datetime')
    
    # 截取到 as_of (再次确认，防止传入的 df 包含未来数据)
    df = df[df['datetime'] <= as_of]
    
    if df.empty:
        # logger.warning(f"No price data before {as_of} for {symbol}")
        return features, raw_stats
    
    # --- 原始统计 ---
    latest_close = _safe_float(df['close'].iloc[-1])
    raw_stats['close_price'] = latest_close
    
    # 窗口内数据
    window_start = as_of - pd.Timedelta(days=window_days)
    window_df = df[df['datetime'] >= window_start]
    
    if not window_df.empty:
        raw_stats['high_window'] = _safe_float(window_df['high'].max())
        raw_stats['low_window'] = _safe_float(window_df['low'].min())
        raw_stats['data_points_window'] = len(window_df)
    else:
        raw_stats['high_window'] = latest_close
        raw_stats['low_window'] = latest_close
        raw_stats['data_points_window'] = 0
    
    # 成交量统计
    if 'volume' in df.columns and not df['volume'].isna().all():
        # 最近 7D 平均成交量
        seven_days_ago = as_of - pd.Timedelta(days=7)
        recent_df = df[df['datetime'] >= seven_days_ago]
        
        if not recent_df.empty:
            avg_volume_7d = _safe_float(recent_df['volume'].mean())
        else:
            avg_volume_7d = 0.0
        
        # 窗口内平均成交量
        if not window_df.empty and 'volume' in window_df.columns:
            avg_volume_window = _safe_float(window_df['volume'].mean())
            std_volume_window = _safe_float(window_df['volume'].std())
        else:
            avg_volume_window = 0.0
            std_volume_window = 0.0
        
        raw_stats['avg_volume_7d'] = avg_volume_7d
        raw_stats['avg_volume_window'] = avg_volume_window
        
        # volume_zscore: 最近 7D 均量相对窗口的 z-score
        features['volume_zscore'] = _compute_zscore(avg_volume_7d, avg_volume_window, std_volume_window)
    else:
        features['volume_zscore'] = 0.0
        raw_stats['avg_volume_7d'] = 0.0
        raw_stats['avg_volume_window'] = 0.0
    
    # --- 收益率特征 ---
    # 计算窗口内累计对数收益
    if not window_df.empty and 'close' in window_df.columns:
        window_return = _compute_log_return(window_df['close'])
        raw_stats['return_window_pct'] = float(np.exp(window_return) - 1)  # 转为百分比形式
    else:
        window_return = 0.0
        raw_stats['return_window_pct'] = 0.0
    
    # 计算历史收益率均值和标准差（用于 z-score）
    # 使用滚动窗口的收益率分布
    if len(df) >= window_days + 5:
        historical_returns = []
        close_series = df['close'].values
        
        # 计算多个历史窗口的收益率
        for i in range(window_days, len(df), max(1, window_days // 2)):
            start_idx = i - window_days
            if start_idx >= 0 and close_series[start_idx] > 0 and close_series[i] > 0:
                ret = np.log(close_series[i] / close_series[start_idx])
                if not np.isnan(ret) and not np.isinf(ret):
                    historical_returns.append(ret)
        
        if len(historical_returns) >= 3:
            ret_mean = np.mean(historical_returns)
            ret_std = np.std(historical_returns, ddof=1)
            features['ret_window'] = _compute_zscore(window_return, ret_mean, ret_std)
        else:
            features['ret_window'] = 0.0
    else:
        features['ret_window'] = 0.0
    
    # --- 波动率特征 ---
    if not window_df.empty and 'close' in window_df.columns:
        window_vol = _compute_volatility(window_df['close'])
        raw_stats['volatility_window'] = window_vol
    else:
        window_vol = 0.0
        raw_stats['volatility_window'] = 0.0
    
    # 计算历史波动率均值和标准差（用于 z-score）
    if len(df) >= window_days + 5:
        historical_vols = []
        
        for i in range(window_days, len(df), max(1, window_days // 2)):
            start_idx = i - window_days
            if start_idx >= 0:
                segment = df.iloc[start_idx:i]['close']
                vol = _compute_volatility(segment)
                if vol > 0:
                    historical_vols.append(vol)
        
        if len(historical_vols) >= 3:
            vol_mean = np.mean(historical_vols)
            vol_std = np.std(historical_vols, ddof=1)
            features['vol_window'] = _compute_zscore(window_vol, vol_mean, vol_std)
        else:
            features['vol_window'] = 0.0
    else:
        features['vol_window'] = 0.0
    
    return features, raw_stats


# ========== 注意力特征计算 ==========

def _compute_attention_features(
    symbol: str,
    as_of: datetime,
    timeframe: str,
    window_days: int,
    attention_df: Optional[pd.DataFrame] = None,
    news_df: Optional[pd.DataFrame] = None,
) -> tuple[Dict[str, float], Dict[str, Any]]:
    """
    计算注意力相关特征
    
    Features (规范化):
    - att_composite_z: 最近 composite_attention_zscore（已经是 z-score）
    - att_news_z: 最近 news_channel_score（已经是 z-score）
    - att_trend_7d: 最近 7D composite_attention_score 的斜率
    - att_spike_flag: 最近 composite_attention_spike_flag (0/1)
    - att_news_share: News 通道占比估计
    - att_google_share: Google Trends 通道占比估计
    - att_twitter_share: Twitter 通道占比估计
    - sentiment_mean_window: 窗口内平均 sentiment_score 的 z-score
    - bullish_minus_bearish: bullish - bearish 的窗口均值 z-score
    
    Raw Stats:
    - composite_attention_score: 最近的合成注意力分数
    - news_count_7d: 最近 7D 的新闻数量
    - google_trend_value: 最近的 Google Trends 值
    - twitter_volume: 最近的 Twitter volume
    - avg_bullish: 窗口内平均 bullish_attention
    - avg_bearish: 窗口内平均 bearish_attention
    
    Parameters
    ----------
    symbol : str
        币种符号
    as_of : datetime
        截止时间
    timeframe : str
        时间粒度
    window_days : int
        窗口天数
    attention_df : pd.DataFrame | None
        预加载的注意力数据
    news_df : pd.DataFrame | None
        预加载的新闻数据
    
    Returns
    -------
    tuple[Dict[str, float], Dict[str, Any]]
        (features, raw_stats)
    """
    features: Dict[str, float] = {}
    raw_stats: Dict[str, Any] = {}
    
    # 加载注意力数据
    lookback_days = max(window_days * 2, 60)  # 确保有足够历史数据
    start_dt = as_of - pd.Timedelta(days=lookback_days)
    
    if attention_df is None:
        df = load_attention_data(symbol, start_dt, as_of)
    else:
        mask = (attention_df['datetime'] > start_dt) & (attention_df['datetime'] <= as_of)
        df = attention_df.loc[mask].copy()
    
    if df.empty:
        # logger.warning(f"No attention data for {symbol}")
        # 返回默认值
        features.update({
            'att_composite_z': 0.0,
            'att_news_z': 0.0,
            'att_trend_7d': 0.0,
            'att_spike_flag': 0.0,
            'att_news_share': 0.0,
            'att_google_share': 0.0,
            'att_twitter_share': 0.0,
            'sentiment_mean_window': 0.0,
            'bullish_minus_bearish': 0.0,
        })
        return features, raw_stats
    
    # 确保 datetime 列存在且为 UTC
    if 'datetime' in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df['datetime']):
            df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
            
        # 确保有时区信息
        if df['datetime'].dt.tz is None:
            df['datetime'] = df['datetime'].dt.tz_localize('UTC')
            
        df = df.sort_values('datetime')
    
    # 截取到 as_of
    df = df[df['datetime'] <= as_of]
    
    if df.empty:
        # logger.warning(f"No attention data before {as_of} for {symbol}")
        features.update({
            'att_composite_z': 0.0,
            'att_news_z': 0.0,
            'att_trend_7d': 0.0,
            'att_spike_flag': 0.0,
            'att_news_share': 0.0,
            'att_google_share': 0.0,
            'att_twitter_share': 0.0,
            'sentiment_mean_window': 0.0,
            'bullish_minus_bearish': 0.0,
        })
        return features, raw_stats
    
    # 获取最新一行数据
    latest = df.iloc[-1]
    
    # --- 直接使用已计算的 z-score ---
    features['att_composite_z'] = _safe_float(latest.get('composite_attention_zscore', 0))
    features['att_news_z'] = _safe_float(latest.get('news_channel_score', 0))
    features['att_spike_flag'] = _safe_float(latest.get('composite_attention_spike_flag', 0))
    
    # 原始统计
    raw_stats['composite_attention_score'] = _safe_float(latest.get('composite_attention_score', 0))
    raw_stats['google_trend_value'] = _safe_float(latest.get('google_trend_value', 0))
    raw_stats['twitter_volume'] = _safe_float(latest.get('twitter_volume', 0))
    raw_stats['google_trend_zscore'] = _safe_float(latest.get('google_trend_zscore', 0))
    raw_stats['twitter_volume_zscore'] = _safe_float(latest.get('twitter_volume_zscore', 0))
    
    # --- 计算 7D 趋势斜率 ---
    seven_days_ago = as_of - pd.Timedelta(days=7)
    recent_df = df[df['datetime'] >= seven_days_ago]
    
    if not recent_df.empty and 'composite_attention_score' in recent_df.columns:
        slope = _compute_slope(recent_df['composite_attention_score'])
        # 对斜率进行标准化（除以历史斜率的标准差）
        if len(df) >= window_days:
            historical_slopes = []
            for i in range(7, len(df)):
                segment = df.iloc[max(0, i-7):i]['composite_attention_score']
                s = _compute_slope(segment)
                if not np.isnan(s):
                    historical_slopes.append(s)
            
            if len(historical_slopes) >= 3:
                slope_std = np.std(historical_slopes, ddof=1)
                features['att_trend_7d'] = _compute_zscore(slope, 0, slope_std)  # 假设均值为 0
            else:
                features['att_trend_7d'] = slope * 10  # 简单放缩
        else:
            features['att_trend_7d'] = slope * 10
    else:
        features['att_trend_7d'] = 0.0
    
    # --- 计算通道占比 ---
    # 基于各通道 z-score 的绝对值估算占比
    news_z = abs(_safe_float(latest.get('news_channel_score', 0)))
    google_z = abs(_safe_float(latest.get('google_trend_zscore', 0)))
    twitter_z = abs(_safe_float(latest.get('twitter_volume_zscore', 0)))
    
    total_z = news_z + google_z + twitter_z
    
    if total_z > 0:
        features['att_news_share'] = news_z / total_z
        features['att_google_share'] = google_z / total_z
        features['att_twitter_share'] = twitter_z / total_z
    else:
        # 默认权重（来自 attention_channels.py）
        features['att_news_share'] = 0.5
        features['att_google_share'] = 0.3
        features['att_twitter_share'] = 0.2
    
    raw_stats['channel_news_zscore'] = news_z
    raw_stats['channel_google_zscore'] = google_z
    raw_stats['channel_twitter_zscore'] = twitter_z
    
    # --- 窗口内统计 ---
    window_start = as_of - pd.Timedelta(days=window_days)
    window_df = df[df['datetime'] >= window_start]
    
    if not window_df.empty:
        # 新闻数量统计
        if 'news_count' in window_df.columns:
            total_news_window = int(window_df['news_count'].sum())
            raw_stats['news_count_window'] = total_news_window
            
            # 7D 新闻数量
            if not recent_df.empty and 'news_count' in recent_df.columns:
                raw_stats['news_count_7d'] = int(recent_df['news_count'].sum())
            else:
                raw_stats['news_count_7d'] = 0
        else:
            raw_stats['news_count_window'] = 0
            raw_stats['news_count_7d'] = 0
        
        # Bullish vs Bearish
        if 'bullish_attention' in window_df.columns and 'bearish_attention' in window_df.columns:
            avg_bullish = _safe_float(window_df['bullish_attention'].mean())
            avg_bearish = _safe_float(window_df['bearish_attention'].mean())
            
            raw_stats['avg_bullish'] = avg_bullish
            raw_stats['avg_bearish'] = avg_bearish
            
            # bullish - bearish 的差值
            diff = avg_bullish - avg_bearish
            
            # 计算历史差值的标准差用于标准化
            if len(df) >= window_days:
                bull_col = df.get('bullish_attention', pd.Series())
                bear_col = df.get('bearish_attention', pd.Series())
                
                if not bull_col.empty and not bear_col.empty:
                    diff_series = bull_col - bear_col
                    diff_std = _safe_float(diff_series.std(ddof=1))
                    features['bullish_minus_bearish'] = _compute_zscore(diff, 0, diff_std)
                else:
                    features['bullish_minus_bearish'] = diff * 10  # 简单放缩
            else:
                features['bullish_minus_bearish'] = diff * 10
        else:
            raw_stats['avg_bullish'] = 0.0
            raw_stats['avg_bearish'] = 0.0
            features['bullish_minus_bearish'] = 0.0
        
        # 窗口内平均 composite score
        if 'composite_attention_score' in window_df.columns:
            raw_stats['avg_composite_score'] = _safe_float(window_df['composite_attention_score'].mean())
        else:
            raw_stats['avg_composite_score'] = 0.0
    else:
        raw_stats['news_count_window'] = 0
        raw_stats['news_count_7d'] = 0
        raw_stats['avg_bullish'] = 0.0
        raw_stats['avg_bearish'] = 0.0
        raw_stats['avg_composite_score'] = 0.0
        features['bullish_minus_bearish'] = 0.0
    
    # --- 情绪特征 ---
    # 尝试从新闻数据获取 sentiment 信息
    if news_df is None:
        news_df_slice = load_news_data(symbol, window_start, as_of)
    else:
        mask = (news_df['datetime'] > window_start) & (news_df['datetime'] <= as_of)
        news_df_slice = news_df.loc[mask].copy()
    
    if not news_df_slice.empty and 'sentiment_score' in news_df_slice.columns:
        sentiment_values = news_df_slice['sentiment_score'].dropna()
        
        if not sentiment_values.empty:
            sentiment_mean = _safe_float(sentiment_values.mean())
            raw_stats['sentiment_mean_window'] = sentiment_mean
            
            # 标准化
            sentiment_std = _safe_float(sentiment_values.std(ddof=1))
            if sentiment_std > 0:
                # 相对于窗口内分布的 z-score
                features['sentiment_mean_window'] = sentiment_mean / sentiment_std
            else:
                features['sentiment_mean_window'] = sentiment_mean * 2  # 简单放缩
        else:
            raw_stats['sentiment_mean_window'] = 0.0
            features['sentiment_mean_window'] = 0.0
    else:
        raw_stats['sentiment_mean_window'] = 0.0
        features['sentiment_mean_window'] = 0.0
    
    return features, raw_stats


# ========== 主函数 ==========

def compute_state_snapshot(
    symbol: str,
    as_of: datetime | None = None,
    timeframe: str = "1d",
    window_days: int = 30,
    price_df: Optional[pd.DataFrame] = None,
    attention_df: Optional[pd.DataFrame] = None,
    news_df: Optional[pd.DataFrame] = None,
) -> StateSnapshot | None:
    """
    基于 Price + AttentionFeature，为给定 symbol 计算截至 as_of 的状态特征向量。
    
    本函数整合价格、波动率和注意力三大维度的多个特征，构建一个规范化的状态快照。
    快照可用于：
    - 相似模式检索：找到历史上状态相似的时刻
    - 情景分析：研究类似状态下的后续价格表现
    - 多因子评估：综合评估当前市场状态
    
    Parameters
    ----------
    symbol : str
        加密货币符号，如 'ZEC', 'BTC'。
        会自动处理 'USDT' 后缀。
    as_of : datetime | None
        快照截止时间（UTC）。
        默认为 None，表示使用当前时间。
    timeframe : str
        数据时间粒度，支持 '1d'（日级）和 '4h'（4小时级）。
        默认 '1d'。
    window_days : int
        用于计算滚动统计的窗口天数。
        默认 30 天。
    price_df : pd.DataFrame | None
        预加载的价格数据（可选）
    attention_df : pd.DataFrame | None
        预加载的注意力数据（可选）
    news_df : pd.DataFrame | None
        预加载的新闻数据（可选）
    
    Returns
    -------
    StateSnapshot | None
        包含规范化特征和原始统计的状态快照。
        如果数据不足以计算任何特征，返回 None。
    
    Features 说明
    -------------
    价格/波动维度：
    - ret_window: 窗口累计对数收益的 z-score，反映近期价格动量
    - vol_window: 窗口波动率的 z-score，反映波动水平相对历史
    - volume_zscore: 近 7D 平均成交量相对窗口均值的 z-score，反映交易活跃度
    
    Attention 维度：
    - att_composite_z: 合成注意力 z-score，综合反映市场关注度
    - att_news_z: 新闻通道 z-score，反映新闻热度
    - att_trend_7d: 近 7D 注意力趋势斜率（标准化），反映关注度变化方向
    - att_spike_flag: 注意力 spike 标志 (0/1)，指示是否处于高关注状态
    
    通道结构：
    - att_news_share: 新闻通道在合成分数中的占比估计
    - att_google_share: Google Trends 通道占比估计
    - att_twitter_share: Twitter 通道占比估计
    
    情绪/新闻维度：
    - sentiment_mean_window: 窗口内平均情绪分数（标准化）
    - bullish_minus_bearish: bullish - bearish 差值的 z-score，反映情绪偏向
    
    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> snapshot = compute_state_snapshot("ZEC")
    >>> if snapshot:
    ...     print(f"Symbol: {snapshot.symbol}")
    ...     print(f"Features: {list(snapshot.features.keys())}")
    
    >>> # 指定时间点
    >>> as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    >>> snapshot = compute_state_snapshot("BTC", as_of=as_of, window_days=60)
    """
    # 参数处理
    symbol = symbol.upper()
    if symbol.endswith('USDT'):
        symbol = symbol[:-4]  # 统一去掉 USDT 后缀
    
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    elif as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    
    # 验证 timeframe
    timeframe = timeframe.lower()
    if timeframe not in ('1d', '4h'):
        logger.warning(f"Unsupported timeframe '{timeframe}', falling back to '1d'")
        timeframe = '1d'
    
    # logger.info(f"Computing state snapshot for {symbol} as_of {as_of} (window={window_days}d, tf={timeframe})")
    
    # 初始化结果
    all_features: Dict[str, float] = {}
    all_raw_stats: Dict[str, Any] = {}
    
    # 1. 计算价格/波动特征
    try:
        price_features, price_stats = _compute_price_features(symbol, as_of, timeframe, window_days, price_df)
        all_features.update(price_features)
        all_raw_stats.update(price_stats)
    except Exception as e:
        logger.error(f"Error computing price features for {symbol}: {e}")
        # 继续，不中断
    
    # 2. 计算注意力特征
    try:
        attention_features, attention_stats = _compute_attention_features(symbol, as_of, timeframe, window_days, attention_df, news_df)
        all_features.update(attention_features)
        all_raw_stats.update(attention_stats)
    except Exception as e:
        logger.error(f"Error computing attention features for {symbol}: {e}")
        # 继续，不中断
    
    # 检查是否有任何有效特征
    non_zero_features = {k: v for k, v in all_features.items() if v != 0.0}
    
    if not non_zero_features and not all_raw_stats:
        # logger.warning(f"No valid features computed for {symbol} as_of {as_of}")
        return None
    
    # 构建快照
    snapshot = StateSnapshot(
        symbol=symbol,
        as_of=as_of,
        timeframe=timeframe,
        window_days=window_days,
        features=all_features,
        raw_stats=all_raw_stats,
    )
    
    # logger.info(
    #     f"State snapshot computed for {symbol}: "
    #     f"{len(all_features)} features, {len(all_raw_stats)} raw stats"
    # )
    
    return snapshot


# ========== 批量计算 ==========

def compute_state_snapshots_batch(
    symbols: List[str],
    as_of: datetime | None = None,
    timeframe: str = "1d",
    window_days: int = 30,
) -> Dict[str, StateSnapshot | None]:
    """
    批量计算多个 symbol 的状态快照
    
    Parameters
    ----------
    symbols : List[str]
        币种列表
    as_of : datetime | None
        快照时间
    timeframe : str
        时间粒度
    window_days : int
        窗口天数
    
    Returns
    -------
    Dict[str, StateSnapshot | None]
        symbol -> snapshot 的映射
    """
    results: Dict[str, StateSnapshot | None] = {}
    
    for symbol in symbols:
        try:
            snapshot = compute_state_snapshot(symbol, as_of, timeframe, window_days)
            results[symbol] = snapshot
        except Exception as e:
            logger.error(f"Error computing snapshot for {symbol}: {e}")
            results[symbol] = None
    
    return results


if __name__ == "__main__":
    # 测试代码
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 计算 ZEC 的状态快照
    snapshot = compute_state_snapshot("ZEC")
    
    if snapshot:
        print(f"\n=== State Snapshot for {snapshot.symbol} ===")
        print(f"As of: {snapshot.as_of}")
        print(f"Timeframe: {snapshot.timeframe}")
        print(f"Window: {snapshot.window_days} days")
        
        print("\n--- Normalized Features ---")
        for k, v in sorted(snapshot.features.items()):
            print(f"  {k}: {v:.4f}")
        
        print("\n--- Raw Stats ---")
        for k, v in sorted(snapshot.raw_stats.items()):
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")
    else:
        print("Failed to compute snapshot")
