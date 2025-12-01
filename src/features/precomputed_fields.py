"""
预计算字段模块

在数据更新时计算并存储派生字段，避免 API 请求时实时计算。

功能：
1. 滚动收益率 (1d/7d/30d/60d)
2. 滚动波动率 (7d/30d/60d)
3. 成交量 z-score (7d/30d)
4. 周期高低点 (30d/60d)
5. 状态特征 (收益率 z-score, 波动率 z-score, 注意力趋势等)
6. 前瞻收益 (3d/7d/30d) - 用于回测
7. 最大回撤 (7d/30d)
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


def compute_rolling_returns(close: pd.Series) -> Dict[str, pd.Series]:
    """计算滚动收益率"""
    return {
        'return_1d': close.pct_change(1),
        'return_7d': close.pct_change(7),
        'return_30d': close.pct_change(30),
        'return_60d': close.pct_change(60),
    }


def compute_rolling_volatility(close: pd.Series) -> Dict[str, pd.Series]:
    """计算滚动波动率 (log return std)"""
    log_ret = np.log(close / close.shift(1))
    return {
        'volatility_7d': log_ret.rolling(7).std() * np.sqrt(365),
        'volatility_30d': log_ret.rolling(30).std() * np.sqrt(365),
        'volatility_60d': log_ret.rolling(60).std() * np.sqrt(365),
    }


def compute_volume_zscore(volume: pd.Series) -> Dict[str, pd.Series]:
    """计算成交量 z-score"""
    def zscore(s, window):
        mean = s.rolling(window).mean()
        std = s.rolling(window).std()
        return (s - mean) / std.replace(0, np.nan)
    
    return {
        'volume_zscore_7d': zscore(volume, 7),
        'volume_zscore_30d': zscore(volume, 30),
    }


def compute_high_low(high: pd.Series, low: pd.Series) -> Dict[str, pd.Series]:
    """计算周期内高低点"""
    return {
        'high_30d': high.rolling(30).max(),
        'low_30d': low.rolling(30).min(),
        'high_60d': high.rolling(60).max(),
        'low_60d': low.rolling(60).min(),
    }


def compute_state_features(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    计算状态特征 (用于 State Snapshot API)
    
    注意：这些计算依赖 close 和 attention_score 字段
    """
    features = {}
    
    # 检查必需的列
    if 'close' not in df.columns:
        if 'close_price' in df.columns:
            df = df.copy()
            df['close'] = df['close_price']
        else:
            logger.warning("compute_state_features: 缺少 close 列")
            return features
    
    # 收益率 z-score
    ret_1d = df['close'].pct_change(1)
    
    for window in [7, 30]:
        mean = ret_1d.rolling(window).mean()
        std = ret_1d.rolling(window).std()
        features[f'feat_ret_zscore_{window}d'] = (ret_1d - mean) / std.replace(0, np.nan)
    
    # 波动率 z-score
    log_ret = np.log(df['close'] / df['close'].shift(1))
    vol_7d = log_ret.rolling(7).std() * np.sqrt(365)
    
    for window in [7, 30]:
        mean = vol_7d.rolling(window).mean()
        std = vol_7d.rolling(window).std()
        features[f'feat_vol_zscore_{window}d'] = (vol_7d - mean) / std.replace(0, np.nan)
    
    # 注意力趋势 (7天变化率)
    if 'composite_attention_score' in df.columns:
        features['feat_att_trend_7d'] = df['composite_attention_score'].pct_change(7)
    elif 'attention_score' in df.columns:
        features['feat_att_trend_7d'] = df['attention_score'].pct_change(7)
    else:
        features['feat_att_trend_7d'] = pd.Series(np.nan, index=df.index)
    
    # 注意力来源占比
    news_score = df.get('news_channel_score', pd.Series(0, index=df.index)).fillna(0)
    google_score = df.get('google_trend_zscore', pd.Series(0, index=df.index)).fillna(0)
    twitter_score = df.get('twitter_volume_zscore', pd.Series(0, index=df.index)).fillna(0)
    
    total = news_score.abs() + google_score.abs() + twitter_score.abs()
    total = total.replace(0, np.nan)
    
    features['feat_att_news_share'] = news_score.abs() / total
    features['feat_att_google_share'] = google_score.abs() / total
    features['feat_att_twitter_share'] = twitter_score.abs() / total
    
    # 多空情绪差
    bullish = df.get('bullish_attention', pd.Series(0, index=df.index)).fillna(0)
    bearish = df.get('bearish_attention', pd.Series(0, index=df.index)).fillna(0)
    total_sentiment = bullish + bearish
    total_sentiment = total_sentiment.replace(0, np.nan)
    features['feat_bullish_minus_bearish'] = (bullish - bearish) / total_sentiment
    
    return features


def compute_forward_returns(close: pd.Series) -> Dict[str, pd.Series]:
    """
    计算前瞻收益 (用于回测)
    
    注意：这些值只有在日期过去后才能计算，当天的值为 NaN
    """
    return {
        'forward_return_3d': close.pct_change(3).shift(-3),
        'forward_return_7d': close.pct_change(7).shift(-7),
        'forward_return_30d': close.pct_change(30).shift(-30),
    }


def compute_max_drawdown(close: pd.Series) -> Dict[str, pd.Series]:
    """计算最大回撤"""
    def max_dd(s, window):
        rolling_max = s.rolling(window, min_periods=1).max()
        drawdown = (s - rolling_max) / rolling_max
        return drawdown.rolling(window).min()
    
    return {
        'max_drawdown_7d': max_dd(close, 7),
        'max_drawdown_30d': max_dd(close, 30),
    }


def compute_feature_vector(row: pd.Series, dim: int = 16) -> Optional[np.ndarray]:
    """
    生成特征向量 (用于 pgvector 相似度搜索)
    
    向量包含：
    - 归一化的收益率 z-score
    - 归一化的波动率 z-score  
    - 归一化的注意力特征
    - 成交量 z-score
    """
    features = []
    
    # 收益率特征
    for col in ['feat_ret_zscore_7d', 'feat_ret_zscore_30d']:
        val = row.get(col, np.nan)
        features.append(np.clip(val, -3, 3) / 3 if pd.notna(val) else 0)
    
    # 波动率特征  
    for col in ['feat_vol_zscore_7d', 'feat_vol_zscore_30d']:
        val = row.get(col, np.nan)
        features.append(np.clip(val, -3, 3) / 3 if pd.notna(val) else 0)
    
    # 注意力特征
    for col in ['feat_att_trend_7d', 'feat_att_news_share', 'feat_att_google_share', 
                'feat_att_twitter_share', 'feat_bullish_minus_bearish']:
        val = row.get(col, np.nan)
        features.append(np.clip(val, -1, 1) if pd.notna(val) else 0)
    
    # 成交量特征
    for col in ['volume_zscore_7d', 'volume_zscore_30d']:
        val = row.get(col, np.nan)
        features.append(np.clip(val, -3, 3) / 3 if pd.notna(val) else 0)
    
    # 收益率/波动率原始值
    for col in ['return_7d', 'return_30d', 'volatility_7d', 'volatility_30d']:
        val = row.get(col, np.nan)
        if pd.notna(val):
            if 'return' in col:
                features.append(np.clip(val, -0.5, 0.5) * 2)
            else:
                features.append(np.clip(val, 0, 2) / 2)
        else:
            features.append(0)
    
    # 补齐到目标维度
    while len(features) < dim:
        features.append(0)
    
    return np.array(features[:dim], dtype=np.float32)


def compute_all_precomputed_fields(
    price_df: pd.DataFrame,
    attention_df: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    计算所有预计算字段
    
    Args:
        price_df: 价格数据，必须包含 datetime, close, open, high, low, volume
        attention_df: 可选的注意力数据，用于计算状态特征
        
    Returns:
        DataFrame 包含所有预计算字段，以 datetime 为索引
    """
    if price_df is None or price_df.empty:
        return pd.DataFrame()
    
    # 确保 datetime 类型
    df = price_df.copy()
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df = df.sort_values('datetime')
        df = df.set_index('datetime')
    elif 'timestamp' in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df = df.sort_values('datetime')
        df = df.set_index('datetime')
    
    result = pd.DataFrame(index=df.index)
    
    # 价格快照
    for col in ['close', 'open', 'high', 'low', 'volume']:
        if col in df.columns:
            result[f'{col}_price' if col != 'volume' else col] = df[col]
    
    # 处理列名映射
    close_col = 'close_price' if 'close_price' in result.columns else 'close'
    if close_col not in result.columns and 'close' in df.columns:
        result['close_price'] = df['close']
        close_col = 'close_price'
    
    if close_col not in result.columns:
        logger.warning("compute_all_precomputed_fields: 缺少 close 列")
        return result
    
    # 滚动收益率
    for name, series in compute_rolling_returns(result[close_col]).items():
        result[name] = series
    
    # 滚动波动率
    for name, series in compute_rolling_volatility(result[close_col]).items():
        result[name] = series
    
    # 成交量 z-score
    if 'volume' in result.columns:
        for name, series in compute_volume_zscore(result['volume']).items():
            result[name] = series
    
    # 高低点
    high_col = 'high_price' if 'high_price' in result.columns else 'high'
    low_col = 'low_price' if 'low_price' in result.columns else 'low'
    
    if high_col in result.columns and low_col in result.columns:
        for name, series in compute_high_low(result[high_col], result[low_col]).items():
            result[name] = series
    elif 'high' in df.columns and 'low' in df.columns:
        for name, series in compute_high_low(df['high'], df['low']).items():
            result[name] = series
    
    # 合并注意力数据并计算状态特征
    if attention_df is not None and not attention_df.empty:
        att_df = attention_df.copy()
        if 'datetime' in att_df.columns:
            att_df['datetime'] = pd.to_datetime(att_df['datetime'], utc=True)
            att_df = att_df.set_index('datetime')
        
        # 合并
        merged = result.join(att_df, how='left', rsuffix='_att')
        merged['close'] = result[close_col]  # 确保有 close 列
        
        for name, series in compute_state_features(merged).items():
            result[name] = series
    else:
        # 只计算基于价格的状态特征
        result['close'] = result[close_col]
        price_only_features = compute_state_features(result)
        for name in ['feat_ret_zscore_7d', 'feat_ret_zscore_30d', 
                     'feat_vol_zscore_7d', 'feat_vol_zscore_30d']:
            if name in price_only_features:
                result[name] = price_only_features[name]
    
    # 前瞻收益
    for name, series in compute_forward_returns(result[close_col]).items():
        result[name] = series
    
    # 最大回撤
    for name, series in compute_max_drawdown(result[close_col]).items():
        result[name] = series
    
    # 清理中间列
    if 'close' in result.columns and close_col == 'close_price':
        result = result.drop(columns=['close'], errors='ignore')
    
    # 替换 inf
    result = result.replace([np.inf, -np.inf], np.nan)
    
    return result


def update_attention_record_with_precomputed(
    attention_record: dict,
    price_row: Optional[dict] = None,
    precomputed_row: Optional[pd.Series] = None
) -> dict:
    """
    更新单条注意力记录，添加预计算字段
    
    用于增量更新时，逐条添加预计算字段。
    
    Args:
        attention_record: 注意力记录 dict
        price_row: 对应的价格数据 dict
        precomputed_row: 预计算字段 Series
        
    Returns:
        更新后的 attention_record
    """
    result = attention_record.copy()
    
    # 添加价格快照
    if price_row:
        for col in ['close', 'open', 'high', 'low', 'volume']:
            if col in price_row:
                result_col = f'{col}_price' if col != 'volume' else col
                result[result_col] = price_row[col]
    
    # 添加预计算字段
    if precomputed_row is not None:
        precomputed_cols = [
            'return_1d', 'return_7d', 'return_30d', 'return_60d',
            'volatility_7d', 'volatility_30d', 'volatility_60d',
            'volume_zscore_7d', 'volume_zscore_30d',
            'high_30d', 'low_30d', 'high_60d', 'low_60d',
            'feat_ret_zscore_7d', 'feat_ret_zscore_30d',
            'feat_vol_zscore_7d', 'feat_vol_zscore_30d',
            'feat_att_trend_7d', 'feat_att_news_share',
            'feat_att_google_share', 'feat_att_twitter_share',
            'feat_bullish_minus_bearish',
            'forward_return_3d', 'forward_return_7d', 'forward_return_30d',
            'max_drawdown_7d', 'max_drawdown_30d',
        ]
        
        for col in precomputed_cols:
            if col in precomputed_row.index:
                val = precomputed_row[col]
                if pd.notna(val):
                    result[col] = float(val)
    
    return result
