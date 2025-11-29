"""
Similar States Module for Crypto Attention Lab

本模块实现历史相似状态检索功能，是 Scenario Engine 的第二步。
基于 StateSnapshot 特征向量，在历史数据中查找与目标状态相似的时刻。

主要功能：
1. 遍历历史数据生成 StateSnapshot 序列
2. 计算特征空间中的距离（欧氏距离/余弦距离）
3. 返回 Top-K 相似的历史状态样本

使用场景：
- 情景分析：找到历史上与当前状态相似的时刻，研究后续价格表现
- 模式识别：发现重复出现的市场状态模式
- 风险评估：基于历史相似状态的表现分布评估潜在风险

注意事项：
- 当前实现为在线计算（实时遍历历史数据），适合研究和中等规模数据
- 生产环境可扩展为离线预计算特征 + 向量数据库方案
- 需要排除目标时间点附近的样本，避免信息泄露
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Iterable, Tuple

import numpy as np
import pandas as pd

from src.data.db_storage import load_price_data, load_attention_data, load_news_data, get_available_symbols
from src.research.state_snapshot import StateSnapshot, compute_state_snapshot, compute_features_vectorized

logger = logging.getLogger(__name__)

# ========== 配置常量 ==========

# 默认历史回溯天数上限（限制计算量）
DEFAULT_MAX_HISTORY_DAYS = 365

# 排除目标时间点附近的天数（避免信息泄露）
DEFAULT_EXCLUSION_DAYS = 7

# 步长配置：每隔多少时间单位计算一个快照
STEP_DAYS_1D = 1  # 日级数据：每天一个快照
STEP_HOURS_4H = 4  # 4H 数据：每 4 小时一个快照


@dataclass
class SimilarState:
    """
    相似状态样本结构
    
    Attributes
    ----------
    symbol : str
        币种符号
    datetime : datetime
        该历史状态的时间点
    timeframe : str
        数据时间粒度 ('1d' 或 '4h')
    distance : float
        与目标状态的特征空间距离（越小越相似）
    similarity : float
        相似度分数 (0-1, 越大越相似)，基于距离转换
    snapshot_summary : Dict[str, Any]
        状态快照摘要，包含关键 raw_stats 便于前端展示
    features : Dict[str, float]
        规范化特征向量（可选，用于调试）
    """
    symbol: str
    datetime: datetime
    timeframe: str
    distance: float
    similarity: float = 0.0
    snapshot_summary: Dict[str, Any] = field(default_factory=dict)
    features: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可 JSON 序列化的字典"""
        result = asdict(self)
        result['datetime'] = self.datetime.isoformat() if self.datetime else None
        return result


# ========== 辅助函数 ==========

def _get_feature_vector(snapshot: StateSnapshot, feature_keys: List[str] | None = None) -> np.ndarray:
    """
    从 StateSnapshot 提取特征向量
    
    Parameters
    ----------
    snapshot : StateSnapshot
        状态快照
    feature_keys : List[str] | None
        要提取的特征键列表，None 表示使用全部特征
    
    Returns
    -------
    np.ndarray
        特征向量
    """
    if feature_keys is None:
        feature_keys = sorted(snapshot.features.keys())
    
    return np.array([snapshot.features.get(k, 0.0) for k in feature_keys])


def _compute_euclidean_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """计算欧氏距离"""
    return float(np.linalg.norm(vec1 - vec2))


def _compute_cosine_distance(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    计算余弦距离 (1 - cosine_similarity)
    
    返回值范围 [0, 2]：
    - 0 表示完全相同方向
    - 1 表示正交
    - 2 表示完全相反方向
    """
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 1.0  # 零向量视为正交
    
    cos_sim = np.dot(vec1, vec2) / (norm1 * norm2)
    # 裁剪到 [-1, 1] 避免浮点误差
    cos_sim = np.clip(cos_sim, -1.0, 1.0)
    
    return float(1.0 - cos_sim)


def _distance_to_similarity(distance: float, scale: float = 1.0) -> float:
    """
    将距离转换为相似度分数 (0-1)
    
    使用指数衰减：similarity = exp(-distance / scale)
    
    Parameters
    ----------
    distance : float
        特征空间距离
    scale : float
        衰减尺度，控制距离对相似度的影响程度
    
    Returns
    -------
    float
        相似度分数 (0, 1]
    """
    return float(np.exp(-distance / scale))


def _create_snapshot_summary(snapshot: StateSnapshot) -> Dict[str, Any]:
    """
    创建快照摘要，提取关键信息用于前端展示
    
    Parameters
    ----------
    snapshot : StateSnapshot
        完整的状态快照
    
    Returns
    -------
    Dict[str, Any]
        摘要信息
    """
    raw = snapshot.raw_stats
    features = snapshot.features
    
    return {
        # 价格信息
        'close_price': raw.get('close_price', 0.0),
        'high_window': raw.get('high_window', 0.0),
        'low_window': raw.get('low_window', 0.0),
        'return_window_pct': raw.get('return_window_pct', 0.0),
        
        # 波动信息
        'volatility_window': raw.get('volatility_window', 0.0),
        
        # 注意力信息
        'composite_attention_score': raw.get('composite_attention_score', 0.0),
        'news_count_7d': raw.get('news_count_7d', 0),
        
        # 情绪信息
        'avg_bullish': raw.get('avg_bullish', 0.0),
        'avg_bearish': raw.get('avg_bearish', 0.0),
        
        # 关键特征
        'ret_window': features.get('ret_window', 0.0),
        'vol_window': features.get('vol_window', 0.0),
        'att_composite_z': features.get('att_composite_z', 0.0),
    }


def _get_historical_dates(
    symbol: str,
    timeframe: str,
    max_history_days: int,
    end_date: datetime | None = None,
) -> List[datetime]:
    """
    获取可用的历史日期列表
    
    Parameters
    ----------
    symbol : str
        币种符号
    timeframe : str
        时间粒度
    max_history_days : int
        最大回溯天数
    end_date : datetime | None
        结束日期，默认为当前时间
    
    Returns
    -------
    List[datetime]
        可用的历史日期列表（升序排列）
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    
    start_date = end_date - timedelta(days=max_history_days)
    
    # 标准化 symbol 格式
    symbol_code = symbol if symbol.endswith('USDT') else f"{symbol}USDT"
    
    # 加载价格数据获取可用日期
    df, _ = load_price_data(symbol_code, timeframe, start_date, end_date)
    
    if df.empty or 'datetime' not in df.columns:
        return []
    
    # 提取唯一日期
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    dates = sorted(df['datetime'].dropna().unique())
    
    return [pd.Timestamp(d).to_pydatetime() for d in dates]


# ========== 核心函数 ==========

def iter_historical_states(
    symbols: List[str],
    timeframe: str = "1d",
    window_days: int = 30,
    max_history_days: int = DEFAULT_MAX_HISTORY_DAYS,
    step_days: int | None = None,
    end_date: datetime | None = None,
    verbose: bool = False,
) -> Iterable[StateSnapshot]:
    """
    遍历给定 symbols 和 timeframe，在历史数据上生成 StateSnapshot 序列。
    
    Parameters
    ----------
    symbols : List[str]
        要遍历的币种列表
    timeframe : str
        时间粒度，'1d' 或 '4h'
    window_days : int
        每个快照的计算窗口天数
    max_history_days : int
        最大回溯历史天数
    step_days : int | None
        步长（天数），None 表示使用默认值（1d=1天，4h=1天内6个点）
    end_date : datetime | None
        结束日期，默认为当前时间
    verbose : bool
        是否打印进度日志
    
    Yields
    ------
    StateSnapshot
        历史状态快照
    
    Notes
    -----
    - 对无效结果（数据不足）会自动跳过
    - 生成的快照按 symbol 分组，每个 symbol 内部按时间升序
    - 需要确保有足够的历史数据（至少 window_days + buffer）
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc)
    
    if step_days is None:
        step_days = STEP_DAYS_1D if timeframe == '1d' else STEP_DAYS_1D
    
    # 确保有足够的历史缓冲 (window_days * 2 + 7 for features)
    lookback_buffer = window_days * 2 + 30
    effective_history = max_history_days + lookback_buffer
    start_date = end_date - timedelta(days=effective_history)
    
    total_yielded = 0
    
    for symbol in symbols:
        symbol = symbol.upper()
        if symbol.endswith('USDT'):
            symbol = symbol[:-4]
        
        if verbose:
            logger.info(f"Processing historical states for {symbol}...")
        
        # 1. 预加载所有数据 (Bulk Load)
        symbol_code = f"{symbol}USDT"
        
        try:
            # 加载价格数据
            price_df, _ = load_price_data(symbol_code, timeframe, start_date, end_date)
            if price_df.empty:
                if verbose: logger.warning(f"No price data for {symbol}")
                continue
                
            if 'datetime' in price_df.columns:
                price_df['datetime'] = pd.to_datetime(price_df['datetime'], utc=True)
                price_df = price_df.sort_values('datetime')
            
            # 加载注意力数据
            attention_df = load_attention_data(symbol, start_date, end_date)
            if not attention_df.empty and 'datetime' in attention_df.columns:
                attention_df['datetime'] = pd.to_datetime(attention_df['datetime'], utc=True)
                attention_df = attention_df.sort_values('datetime')
            
            # 加载新闻数据 (Vectorized computation currently doesn't use news_df heavily, but we pass it)
            # news_df = load_news_data(symbol, start_date, end_date)
            # if not news_df.empty and 'datetime' in news_df.columns:
            #     news_df['datetime'] = pd.to_datetime(news_df['datetime'], utc=True)
            #     news_df = news_df.sort_values('datetime')
                
        except Exception as e:
            logger.error(f"Failed to load data for {symbol}: {e}")
            continue

        # 2. Vectorized Computation
        try:
            features_df = compute_features_vectorized(
                symbol=symbol,
                price_df=price_df,
                attention_df=attention_df,
                timeframe=timeframe,
                window_days=window_days
            )
            
            if features_df.empty:
                continue
                
            # 3. Filter by date range and step
            history_start = end_date - timedelta(days=max_history_days)
            
            # Filter dates >= history_start
            mask = features_df.index >= history_start
            target_df = features_df[mask]
            
            if target_df.empty:
                continue
                
            # Apply step
            # Since index is datetime, we can't just slice by step if there are gaps
            # But assuming daily data is mostly contiguous
            if timeframe == '1d':
                target_df = target_df.iloc[::step_days]
            else:
                target_df = target_df.iloc[::step_days]
            
            symbol_count = 0
            
            # 4. Yield Snapshots
            for dt, row in target_df.iterrows():
                # Extract features and raw stats
                feat_cols = [c for c in row.index if c.startswith('feat_')]
                raw_cols = [c for c in row.index if c.startswith('raw_')]
                
                features = {c[5:]: float(row[c]) for c in feat_cols}
                raw_stats = {c[4:]: row[c] for c in raw_cols}
                
                # Ensure as_of is datetime
                as_of = dt.to_pydatetime() if isinstance(dt, pd.Timestamp) else dt
                
                snapshot = StateSnapshot(
                    symbol=symbol,
                    as_of=as_of,
                    timeframe=timeframe,
                    window_days=window_days,
                    features=features,
                    raw_stats=raw_stats
                )
                
                yield snapshot
                symbol_count += 1
                total_yielded += 1
                
            if verbose:
                logger.info(f"Generated {symbol_count} snapshots for {symbol}")
                
        except Exception as e:
            logger.error(f"Vectorized computation failed for {symbol}: {e}")
            continue
    
    if verbose:
        logger.info(f"Total historical snapshots generated: {total_yielded}")


def find_similar_states(
    target: StateSnapshot,
    candidate_symbols: List[str] | None = None,
    timeframe: str = "1d",
    window_days: int = 30,
    max_candidates: int = 5000,
    top_k: int = 100,
    max_history_days: int = DEFAULT_MAX_HISTORY_DAYS,
    exclusion_days: int = DEFAULT_EXCLUSION_DAYS,
    distance_metric: str = "euclidean",
    include_same_symbol: bool = True,
    verbose: bool = False,
) -> List[SimilarState]:
    """
    在历史中查找与 target 特征相似的状态点。
    
    Parameters
    ----------
    target : StateSnapshot
        目标状态快照
    candidate_symbols : List[str] | None
        候选币种列表，None 表示使用所有可用币种
    timeframe : str
        时间粒度
    window_days : int
        快照计算窗口
    max_candidates : int
        最大候选样本数量（限制计算量）
    top_k : int
        返回的相似样本数量
    max_history_days : int
        最大历史回溯天数
    exclusion_days : int
        排除目标时间点附近的天数（避免信息泄露）
    distance_metric : str
        距离度量方式：'euclidean'（欧氏距离）或 'cosine'（余弦距离）
    include_same_symbol : bool
        是否包含与目标相同的 symbol
    verbose : bool
        是否打印详细日志
    
    Returns
    -------
    List[SimilarState]
        按距离从小到大排序的相似状态列表
    
    Notes
    -----
    - 排除目标时间点 ± exclusion_days 内的样本，避免信息泄露
    - 如果 include_same_symbol=False，会排除与目标相同 symbol 的所有样本
    - 当候选样本不足时，会返回所有可用样本
    """
    # 获取候选币种列表
    if candidate_symbols is None:
        candidate_symbols = get_available_symbols()
    
    if not candidate_symbols:
        logger.warning("No candidate symbols available")
        return []
    
    # 提取目标特征向量
    target_feature_keys = sorted(target.features.keys())
    target_vector = _get_feature_vector(target, target_feature_keys)
    
    if np.all(target_vector == 0):
        logger.warning("Target feature vector is all zeros")
        return []
    
    # 选择距离函数
    if distance_metric == "cosine":
        distance_func = _compute_cosine_distance
        similarity_scale = 0.5  # 余弦距离范围 [0, 2]，使用较小的 scale
    else:
        distance_func = _compute_euclidean_distance
        similarity_scale = 2.0  # 欧氏距离通常较大，使用较大的 scale
    
    # 计算排除时间范围
    exclusion_start = target.as_of - timedelta(days=exclusion_days)
    exclusion_end = target.as_of + timedelta(days=exclusion_days)
    
    if verbose:
        logger.info(
            f"Finding similar states for {target.symbol} @ {target.as_of}\n"
            f"  Candidates: {len(candidate_symbols)} symbols\n"
            f"  Max candidates: {max_candidates}, Top-K: {top_k}\n"
            f"  Exclusion window: {exclusion_start} - {exclusion_end}"
        )
    
    # 收集候选快照
    candidates: List[Tuple[StateSnapshot, float]] = []
    processed_count = 0
    
    for snapshot in iter_historical_states(
        symbols=candidate_symbols,
        timeframe=timeframe,
        window_days=window_days,
        max_history_days=max_history_days,
        end_date=target.as_of + timedelta(days=1),  # 包含目标日期附近
        verbose=False,
    ):
        # 检查是否超过最大候选数
        if processed_count >= max_candidates:
            if verbose:
                logger.info(f"Reached max candidates limit: {max_candidates}")
            break
        
        # 排除相同 symbol（如果设置）
        if not include_same_symbol and snapshot.symbol == target.symbol:
            continue
        
        # 排除时间排除窗口内的样本
        if exclusion_start <= snapshot.as_of <= exclusion_end:
            continue
        
        # 提取候选特征向量
        candidate_vector = _get_feature_vector(snapshot, target_feature_keys)
        
        # 计算距离
        distance = distance_func(target_vector, candidate_vector)
        
        candidates.append((snapshot, distance))
        processed_count += 1
    
    if not candidates:
        if verbose:
            logger.warning("No valid candidates found")
        return []
    
    if verbose:
        logger.info(f"Processed {processed_count} candidates, found {len(candidates)} valid")
    
    # 按距离排序
    candidates.sort(key=lambda x: x[1])
    
    # 取 Top-K
    top_candidates = candidates[:top_k]
    
    # 计算相似度分数的归一化参数
    if top_candidates:
        min_dist = top_candidates[0][1]
        max_dist = top_candidates[-1][1]
        dist_range = max_dist - min_dist if max_dist > min_dist else 1.0
    else:
        dist_range = 1.0
    
    # 构建结果
    results: List[SimilarState] = []
    
    for snapshot, distance in top_candidates:
        similarity = _distance_to_similarity(distance, scale=similarity_scale)
        
        similar_state = SimilarState(
            symbol=snapshot.symbol,
            datetime=snapshot.as_of,
            timeframe=snapshot.timeframe,
            distance=distance,
            similarity=similarity,
            snapshot_summary=_create_snapshot_summary(snapshot),
            features=snapshot.features,
        )
        
        results.append(similar_state)
    
    if verbose:
        logger.info(f"Returning {len(results)} similar states")
    
    return results


def find_similar_states_for_symbol(
    symbol: str,
    timeframe: str = "1d",
    window_days: int = 30,
    top_k: int = 50,
    candidate_symbols: List[str] | None = None,
    max_history_days: int = DEFAULT_MAX_HISTORY_DAYS,
    verbose: bool = False,
) -> Tuple[StateSnapshot | None, List[SimilarState]]:
    """
    便捷函数：计算当前 symbol 的状态快照，并查找相似历史状态
    
    Parameters
    ----------
    symbol : str
        目标币种
    timeframe : str
        时间粒度
    window_days : int
        窗口天数
    top_k : int
        返回的相似样本数
    candidate_symbols : List[str] | None
        候选币种列表
    max_history_days : int
        最大历史回溯天数
    verbose : bool
        是否打印日志
    
    Returns
    -------
    Tuple[StateSnapshot | None, List[SimilarState]]
        (目标快照, 相似状态列表)
    """
    # 计算目标状态
    target = compute_state_snapshot(
        symbol=symbol,
        as_of=None,  # 当前时间
        timeframe=timeframe,
        window_days=window_days,
    )
    
    if target is None:
        logger.warning(f"Failed to compute target snapshot for {symbol}")
        return None, []
    
    # 查找相似状态
    similar_states = find_similar_states(
        target=target,
        candidate_symbols=candidate_symbols,
        timeframe=timeframe,
        window_days=window_days,
        top_k=top_k,
        max_history_days=max_history_days,
        verbose=verbose,
    )
    
    return target, similar_states


if __name__ == "__main__":
    # 测试代码
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Testing Similar States Module")
    print("=" * 60)
    
    # 测试查找 ZEC 的相似历史状态
    target, similar_states = find_similar_states_for_symbol(
        symbol="ZEC",
        timeframe="1d",
        window_days=30,
        top_k=10,
        max_history_days=180,
        verbose=True,
    )
    
    if target:
        print(f"\n=== Target Snapshot ===")
        print(f"Symbol: {target.symbol}")
        print(f"As of: {target.as_of}")
        print(f"Key features:")
        print(f"  ret_window: {target.features.get('ret_window', 0):.4f}")
        print(f"  vol_window: {target.features.get('vol_window', 0):.4f}")
        print(f"  att_composite_z: {target.features.get('att_composite_z', 0):.4f}")
    
    if similar_states:
        print(f"\n=== Top {len(similar_states)} Similar States ===")
        for i, state in enumerate(similar_states[:5]):
            print(f"\n{i+1}. {state.symbol} @ {state.datetime.strftime('%Y-%m-%d')}")
            print(f"   Distance: {state.distance:.4f}, Similarity: {state.similarity:.4f}")
            print(f"   Close: ${state.snapshot_summary.get('close_price', 0):.2f}")
            print(f"   Return: {state.snapshot_summary.get('return_window_pct', 0)*100:.2f}%")
    else:
        print("\nNo similar states found")
