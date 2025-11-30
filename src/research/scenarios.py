"""
Scenario Analysis Module for Crypto Attention Lab

本模块实现 Scenario Engine 的第三步：基于相似状态样本的未来情景分析。
根据历史相似状态的后续价格表现，生成多种可能的未来情景摘要。

主要功能：
1. 获取相似状态样本的未来价格数据
2. 计算各时间窗口的收益率和最大回撤
3. 基于规则将样本分类到不同情景（trend_up, spike_and_revert, sideways 等）
4. 统计各情景的概率、平均收益和风险指标

使用场景：
- 趋势推演：基于历史相似模式预测可能的未来走势
- 风险评估：评估不同情景的概率及潜在收益/风险
- 决策支持：为交易决策提供数据驱动的情景分析

重要声明：
- 当前实现为 rule-based/统计版，用于研究和趋势推演
- 不构成交易建议，过往表现不代表未来收益
- 后续可替换为 ML/聚类方法以提升分类精度

设计理念：
1. 模块化：分类规则与统计计算分离，便于替换分类方法
2. 可扩展：支持自定义分类规则和 lookahead 窗口
3. 透明性：保留原始样本数据，便于验证和调试
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict

import numpy as np
import pandas as pd

from src.services.market_data_service import MarketDataService
from src.research.state_snapshot import StateSnapshot
from src.research.similar_states import SimilarState

logger = logging.getLogger(__name__)

# ========== 配置常量 ==========

# 默认 lookahead 窗口（天数）
DEFAULT_LOOKAHEAD_DAYS = [3, 7, 30]

# 分类阈值配置（可根据数据特性调整）
# --------------------------------------------------
# 这些阈值用于 rule-based 情景分类
# 后续可替换为 ML 模型或 K-means 聚类
# --------------------------------------------------

# 收益率阈值
THRESHOLD_TREND_UP = 0.05       # 7D 收益 > 5% 视为上涨趋势
THRESHOLD_TREND_DOWN = -0.05   # 7D 收益 < -5% 视为下跌趋势
THRESHOLD_SPIKE = 0.03          # 3D 收益 > 3% 视为短期冲高
THRESHOLD_SMALL = 0.02          # |收益| < 2% 视为横盘/微小波动
THRESHOLD_REVERT = 0.02         # 7D 回撤到 spike 后的 2% 以内

# 最大回撤阈值
THRESHOLD_DD_SMALL = -0.05      # 回撤 > -5% 视为小幅回撤
THRESHOLD_DD_LARGE = -0.15      # 回撤 < -15% 视为大幅回撤


@dataclass
class ScenarioSummary:
    """
    情景摘要结构
    
    Attributes
    ----------
    label : str
        情景标签，如 'trend_up', 'spike_and_revert', 'sideways', 'trend_down', 'crash'
    description : str
        人类可读的情景描述
    sample_count : int
        属于该情景的样本数量
    probability : float
        相对样本占比（0-1），作为"概率感"的参考
    avg_return_3d : float | None
        该情景下的 3 日平均收益率
    avg_return_7d : float | None
        该情景下的 7 日平均收益率
    avg_return_30d : float | None
        该情景下的 30 日平均收益率
    max_drawdown_7d : float | None
        该情景下的 7 日平均最大回撤
    max_drawdown_30d : float | None
        该情景下的 30 日平均最大回撤
    avg_path : List[float] | None
        可选：用于画图的平均路径（相对起点的标准化轨迹）
    sample_details : List[Dict] | None
        可选：该情景下的样本详情列表
    """
    label: str
    description: str
    sample_count: int
    probability: float
    avg_return_3d: Optional[float] = None
    avg_return_7d: Optional[float] = None
    avg_return_30d: Optional[float] = None
    max_drawdown_7d: Optional[float] = None
    max_drawdown_30d: Optional[float] = None
    avg_path: Optional[List[float]] = None
    sample_details: Optional[List[Dict]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可 JSON 序列化的字典"""
        result = asdict(self)
        return result


@dataclass
class SampleFuturePerformance:
    """
    单个样本的未来表现数据
    
    Attributes
    ----------
    symbol : str
        币种符号
    start_datetime : datetime
        样本的起始时间点
    returns : Dict[int, float]
        各 lookahead 天数对应的累计对数收益
    max_drawdowns : Dict[int, float]
        各 lookahead 天数对应的最大回撤
    price_path : List[float] | None
        相对起点的价格路径（用于可视化）
    scenario_label : str | None
        分配的情景标签
    """
    symbol: str
    start_datetime: datetime
    returns: Dict[int, float] = field(default_factory=dict)
    max_drawdowns: Dict[int, float] = field(default_factory=dict)
    price_path: Optional[List[float]] = None
    scenario_label: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可 JSON 序列化的字典"""
        return {
            'symbol': self.symbol,
            'start_datetime': self.start_datetime.isoformat() if self.start_datetime else None,
            'returns': self.returns,
            'max_drawdowns': self.max_drawdowns,
            'price_path': self.price_path,
            'scenario_label': self.scenario_label,
        }


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


def _compute_log_return(start_price: float, end_price: float) -> float:
    """
    计算对数收益率
    
    Parameters
    ----------
    start_price : float
        起始价格
    end_price : float
        结束价格
    
    Returns
    -------
    float
        对数收益率 ln(end_price / start_price)
    """
    if start_price <= 0 or end_price <= 0:
        return 0.0
    return float(np.log(end_price / start_price))


def _compute_max_drawdown(prices: pd.Series) -> float:
    """
    计算最大回撤
    
    从价格序列计算最大回撤（负数表示）
    
    Parameters
    ----------
    prices : pd.Series
        价格序列
    
    Returns
    -------
    float
        最大回撤（负数），例如 -0.15 表示 15% 回撤
    """
    if prices.empty or len(prices) < 2:
        return 0.0
    
    # 计算累计最高价
    running_max = prices.cummax()
    
    # 计算回撤
    drawdown = (prices - running_max) / running_max
    
    # 最大回撤（负数）
    max_dd = drawdown.min()
    
    return float(max_dd) if not np.isnan(max_dd) else 0.0


def _get_future_prices(
    symbol: str,
    start_datetime: datetime,
    lookahead_days: int,
    timeframe: str = "1d",
) -> pd.DataFrame:
    """
    获取指定时间点之后的价格数据
    
    Parameters
    ----------
    symbol : str
        币种符号
    start_datetime : datetime
        起始时间点
    lookahead_days : int
        向前看的天数
    timeframe : str
        时间粒度
    
    Returns
    -------
    pd.DataFrame
        价格数据，包含 datetime, close 等列
    """
    # 标准化 symbol 格式
    symbol_code = symbol if symbol.endswith('USDT') else f"{symbol}USDT"
    
    # 计算结束时间（多取几天作为缓冲）
    end_datetime = start_datetime + timedelta(days=lookahead_days + 5)
    
    # 加载价格数据
    df = MarketDataService.get_price_data(symbol_code, timeframe, start_datetime, end_datetime)
    
    if df.empty:
        return pd.DataFrame()
    
    # 确保 datetime 列存在且为 UTC
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        df = df.sort_values('datetime')
    
    # 只保留起始时间之后的数据
    df = df[df['datetime'] >= start_datetime]
    
    return df


# ========== 样本未来表现计算 ==========

def compute_sample_future_performance(
    similar_state: SimilarState,
    lookahead_days: List[int] = DEFAULT_LOOKAHEAD_DAYS,
    timeframe: str = "1d",
    price_df: Optional[pd.DataFrame] = None,
) -> Optional[SampleFuturePerformance]:
    """
    计算单个相似状态样本的未来表现
    
    Parameters
    ----------
    similar_state : SimilarState
        相似状态样本
    lookahead_days : List[int]
        lookahead 窗口列表
    timeframe : str
        时间粒度
    price_df : pd.DataFrame | None
        预加载的价格数据（可选）
    
    Returns
    -------
    SampleFuturePerformance | None
        样本的未来表现数据，数据不足时返回 None
    """
    symbol = similar_state.symbol
    start_dt = similar_state.datetime
    max_lookahead = max(lookahead_days)
    
    # 获取未来价格数据
    if price_df is None:
        future_df = _get_future_prices(symbol, start_dt, max_lookahead, timeframe)
    else:
        # 从预加载数据中切片
        # 假设 price_df 已经包含所需列且 datetime 为 UTC
        end_dt = start_dt + timedelta(days=max_lookahead + 5)
        mask = (price_df['datetime'] >= start_dt) & (price_df['datetime'] <= end_dt)
        future_df = price_df.loc[mask].copy()
    
    if future_df.empty or 'close' not in future_df.columns:
        # logger.debug(f"No future price data for {symbol} @ {start_dt}")
        return None
    
    # 获取起始价格
    if len(future_df) < 2:
        return None
    
    start_price = _safe_float(future_df['close'].iloc[0])
    if start_price <= 0:
        return None
    
    # 计算各 lookahead 窗口的收益和回撤
    returns: Dict[int, float] = {}
    max_drawdowns: Dict[int, float] = {}
    
    for days in lookahead_days:
        # 截取到 lookahead 天数
        cutoff_dt = start_dt + timedelta(days=days)
        window_df = future_df[future_df['datetime'] <= cutoff_dt]
        
        if window_df.empty:
            continue
        
        # 计算累计收益
        end_price = _safe_float(window_df['close'].iloc[-1])
        if end_price > 0:
            returns[days] = _compute_log_return(start_price, end_price)
        
        # 计算最大回撤
        if len(window_df) >= 2:
            max_drawdowns[days] = _compute_max_drawdown(window_df['close'])
    
    # 生成相对起点的价格路径（用于可视化）
    # 取最长 lookahead 窗口的数据
    max_days = max(lookahead_days)
    cutoff_dt = start_dt + timedelta(days=max_days)
    path_df = future_df[future_df['datetime'] <= cutoff_dt]
    
    price_path = None
    if not path_df.empty:
        # 相对起点的百分比变化
        price_path = [(p / start_price - 1) for p in path_df['close'].values]
    
    return SampleFuturePerformance(
        symbol=symbol,
        start_datetime=start_dt,
        returns=returns,
        max_drawdowns=max_drawdowns,
        price_path=price_path,
    )


def compute_all_sample_performances(
    similar_states: List[SimilarState],
    lookahead_days: List[int] = DEFAULT_LOOKAHEAD_DAYS,
    timeframe: str = "1d",
) -> List[SampleFuturePerformance]:
    """
    批量计算所有相似状态样本的未来表现
    
    Parameters
    ----------
    similar_states : List[SimilarState]
        相似状态样本列表
    lookahead_days : List[int]
        lookahead 窗口列表
    timeframe : str
        时间粒度
    
    Returns
    -------
    List[SampleFuturePerformance]
        样本未来表现列表（已过滤无效样本）
    """
    performances = []
    
    # Group by symbol to optimize data loading
    states_by_symbol = defaultdict(list)
    for s in similar_states:
        states_by_symbol[s.symbol].append(s)
        
    max_lookahead = max(lookahead_days)
    
    for symbol, states in states_by_symbol.items():
        try:
            # Determine date range for bulk load
            min_date = min(s.datetime for s in states)
            max_date = max(s.datetime for s in states) + timedelta(days=max_lookahead + 5)
            
            # Load data once per symbol
            symbol_code = symbol if symbol.endswith('USDT') else f"{symbol}USDT"
            df = MarketDataService.get_price_data(symbol_code, timeframe, min_date, max_date)
            
            if not df.empty and 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
                df = df.sort_values('datetime')
            
            for state in states:
                try:
                    perf = compute_sample_future_performance(
                        similar_state=state,
                        lookahead_days=lookahead_days,
                        timeframe=timeframe,
                        price_df=df
                    )
                    if perf is not None:
                        performances.append(perf)
                except Exception as e:
                    # logger.warning(f"Error computing performance for {state.symbol} @ {state.datetime}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error processing batch for {symbol}: {e}")
            continue
    
    logger.info(f"Computed future performance for {len(performances)}/{len(similar_states)} samples")
    return performances


# ========== 情景分类 ==========

def classify_scenario(
    performance: SampleFuturePerformance,
    lookahead_days: List[int] = DEFAULT_LOOKAHEAD_DAYS,
) -> str:
    """
    基于规则将样本分类到情景标签
    
    分类规则（Rule-based）：
    --------------------------------------------------
    1. trend_up: 7D/30D 收益显著为正，且回撤有限
       - ret_7d > THRESHOLD_TREND_UP AND max_dd_7d > THRESHOLD_DD_SMALL
    
    2. trend_down: 7D/30D 收益显著为负
       - ret_7d < THRESHOLD_TREND_DOWN
    
    3. spike_and_revert: 前几天涨幅较大，但 7D 收益接近 0 或转负
       - ret_3d > THRESHOLD_SPIKE AND ret_7d < THRESHOLD_SMALL
    
    4. crash: 大幅下跌，回撤超过阈值
       - max_dd_7d < THRESHOLD_DD_LARGE OR max_dd_30d < THRESHOLD_DD_LARGE
    
    5. sideways: 收益整体接近 0，波动不大（默认情况）
    
    注意：
    - 当前为简单 rule-based 实现，后续可替换为 ML 聚类
    - 规则优先级：crash > trend_up > spike_and_revert > trend_down > sideways
    --------------------------------------------------
    
    Parameters
    ----------
    performance : SampleFuturePerformance
        样本的未来表现数据
    lookahead_days : List[int]
        lookahead 窗口列表
    
    Returns
    -------
    str
        情景标签
    """
    # 获取各窗口的收益和回撤
    ret_3d = performance.returns.get(3, 0.0)
    ret_7d = performance.returns.get(7, 0.0)
    ret_30d = performance.returns.get(30, 0.0)
    
    dd_7d = performance.max_drawdowns.get(7, 0.0)
    dd_30d = performance.max_drawdowns.get(30, 0.0)
    
    # ============================================================
    # 规则判断（按优先级从高到低）
    # ============================================================
    
    # 1. crash: 大幅回撤
    if dd_7d < THRESHOLD_DD_LARGE or dd_30d < THRESHOLD_DD_LARGE:
        return "crash"
    
    # 2. trend_up: 持续上涨且回撤可控
    if ret_7d > THRESHOLD_TREND_UP and dd_7d > THRESHOLD_DD_SMALL:
        return "trend_up"
    
    # 3. spike_and_revert: 冲高回落
    #    3D 涨幅明显，但 7D 收益回撤到接近 0 或转负
    if ret_3d > THRESHOLD_SPIKE and ret_7d < THRESHOLD_SMALL:
        return "spike_and_revert"
    
    # 4. trend_down: 持续下跌
    if ret_7d < THRESHOLD_TREND_DOWN:
        return "trend_down"
    
    # 5. sideways: 默认情况
    return "sideways"


def classify_all_samples(
    performances: List[SampleFuturePerformance],
    lookahead_days: List[int] = DEFAULT_LOOKAHEAD_DAYS,
) -> List[SampleFuturePerformance]:
    """
    对所有样本进行情景分类
    
    Parameters
    ----------
    performances : List[SampleFuturePerformance]
        样本未来表现列表
    lookahead_days : List[int]
        lookahead 窗口列表
    
    Returns
    -------
    List[SampleFuturePerformance]
        已标注情景标签的样本列表
    """
    for perf in performances:
        perf.scenario_label = classify_scenario(perf, lookahead_days)
    
    return performances


# ========== 情景描述 ==========

SCENARIO_DESCRIPTIONS = {
    "trend_up": "持续上涨：价格在观察期内持续走高，回撤可控，适合趋势跟踪策略",
    "trend_down": "持续下跌：价格在观察期内持续走低，建议谨慎或观望",
    "spike_and_revert": "冲高回落：短期内快速上涨后回吐大部分涨幅，可能存在套利机会但需快速决策",
    "crash": "急剧下跌：出现大幅回撤，风险较高，建议规避或设置严格止损",
    "sideways": "横盘震荡：价格波动有限，方向不明确，适合区间操作或观望",
}


# ========== 情景聚合与统计 ==========

def aggregate_scenarios(
    performances: List[SampleFuturePerformance],
    lookahead_days: List[int] = DEFAULT_LOOKAHEAD_DAYS,
    include_sample_details: bool = False,
    max_path_length: int = 30,
) -> List[ScenarioSummary]:
    """
    将分类后的样本聚合为情景摘要列表
    
    Parameters
    ----------
    performances : List[SampleFuturePerformance]
        已标注情景标签的样本列表
    lookahead_days : List[int]
        lookahead 窗口列表
    include_sample_details : bool
        是否包含样本详情
    max_path_length : int
        平均路径的最大长度
    
    Returns
    -------
    List[ScenarioSummary]
        情景摘要列表，按概率从高到低排序
    """
    if not performances:
        return []
    
    # 按情景标签分组
    grouped: Dict[str, List[SampleFuturePerformance]] = defaultdict(list)
    for perf in performances:
        label = perf.scenario_label or "sideways"
        grouped[label].append(perf)
    
    total_samples = len(performances)
    summaries: List[ScenarioSummary] = []
    
    for label, samples in grouped.items():
        sample_count = len(samples)
        probability = sample_count / total_samples if total_samples > 0 else 0.0
        
        # 计算各窗口的平均收益
        avg_return_3d = None
        avg_return_7d = None
        avg_return_30d = None
        
        if 3 in lookahead_days:
            rets_3d = [s.returns.get(3) for s in samples if s.returns.get(3) is not None]
            if rets_3d:
                avg_return_3d = float(np.mean(rets_3d))
        
        if 7 in lookahead_days:
            rets_7d = [s.returns.get(7) for s in samples if s.returns.get(7) is not None]
            if rets_7d:
                avg_return_7d = float(np.mean(rets_7d))
        
        if 30 in lookahead_days:
            rets_30d = [s.returns.get(30) for s in samples if s.returns.get(30) is not None]
            if rets_30d:
                avg_return_30d = float(np.mean(rets_30d))
        
        # 计算平均最大回撤
        max_drawdown_7d = None
        max_drawdown_30d = None
        
        if 7 in lookahead_days:
            dds_7d = [s.max_drawdowns.get(7) for s in samples if s.max_drawdowns.get(7) is not None]
            if dds_7d:
                max_drawdown_7d = float(np.mean(dds_7d))
        
        if 30 in lookahead_days:
            dds_30d = [s.max_drawdowns.get(30) for s in samples if s.max_drawdowns.get(30) is not None]
            if dds_30d:
                max_drawdown_30d = float(np.mean(dds_30d))
        
        # 计算平均价格路径
        avg_path = _compute_average_path(samples, max_path_length)
        
        # 可选：样本详情
        sample_details = None
        if include_sample_details:
            sample_details = [s.to_dict() for s in samples[:20]]  # 限制数量
        
        # 获取描述
        description = SCENARIO_DESCRIPTIONS.get(label, "未知情景")
        
        summary = ScenarioSummary(
            label=label,
            description=description,
            sample_count=sample_count,
            probability=probability,
            avg_return_3d=avg_return_3d,
            avg_return_7d=avg_return_7d,
            avg_return_30d=avg_return_30d,
            max_drawdown_7d=max_drawdown_7d,
            max_drawdown_30d=max_drawdown_30d,
            avg_path=avg_path,
            sample_details=sample_details,
        )
        
        summaries.append(summary)
    
    # 按概率从高到低排序
    summaries.sort(key=lambda x: x.probability, reverse=True)
    
    return summaries


def _compute_average_path(
    samples: List[SampleFuturePerformance],
    max_length: int = 30,
) -> Optional[List[float]]:
    """
    计算样本的平均价格路径
    
    Parameters
    ----------
    samples : List[SampleFuturePerformance]
        样本列表
    max_length : int
        最大路径长度
    
    Returns
    -------
    List[float] | None
        平均路径，或 None 如果无有效路径
    """
    # 收集所有有效路径
    valid_paths = []
    for s in samples:
        if s.price_path and len(s.price_path) >= 2:
            # 截取到最大长度
            path = s.price_path[:max_length]
            valid_paths.append(path)
    
    if not valid_paths:
        return None
    
    # 找到最短路径长度
    min_len = min(len(p) for p in valid_paths)
    
    if min_len < 2:
        return None
    
    # 对齐并计算平均
    aligned_paths = [p[:min_len] for p in valid_paths]
    avg_path = np.mean(aligned_paths, axis=0).tolist()
    
    return avg_path


# ========== 主函数 ==========

def analyze_scenarios(
    target: StateSnapshot,
    similar_states: List[SimilarState],
    lookahead_days: List[int] = DEFAULT_LOOKAHEAD_DAYS,
    include_sample_details: bool = False,
) -> List[ScenarioSummary]:
    """
    对相似状态样本的未来价格路径进行聚合，生成若干情景摘要。
    
    这是 Scenario Engine 的核心函数，完成以下流程：
    1. 对每个 SimilarState，获取其对应 (symbol, datetime) 之后的价格数据
    2. 计算各 lookahead 天数的对数收益和最大回撤
    3. 基于规则将样本分类到不同情景
    4. 统计各情景的概率、平均收益和风险指标
    
    Parameters
    ----------
    target : StateSnapshot
        目标状态快照（用于上下文，暂未使用）
    similar_states : List[SimilarState]
        相似状态样本列表
    lookahead_days : List[int]
        lookahead 窗口列表，默认 [3, 7, 30]
    include_sample_details : bool
        是否在结果中包含样本详情
    
    Returns
    -------
    List[ScenarioSummary]
        情景摘要列表，按概率从高到低排序
    
    Notes
    -----
    - 当前为 rule-based 实现，后续可替换为 ML/聚类方法
    - 样本数量不足时结果可能不具统计意义
    - 过往表现不代表未来收益
    
    Examples
    --------
    >>> from src.research.state_snapshot import compute_state_snapshot
    >>> from src.research.similar_states import find_similar_states
    >>> from src.research.scenarios import analyze_scenarios
    >>> 
    >>> target = compute_state_snapshot("ZEC")
    >>> similar = find_similar_states(target, top_k=100)
    >>> scenarios = analyze_scenarios(target, similar)
    >>> 
    >>> for s in scenarios:
    ...     print(f"{s.label}: {s.probability:.1%} ({s.sample_count} samples)")
    ...     print(f"  7D avg return: {s.avg_return_7d:.2%}")
    """
    if not similar_states:
        logger.warning("No similar states provided for scenario analysis")
        return []
    
    timeframe = target.timeframe if target else "1d"
    
    logger.info(
        f"Analyzing scenarios for {len(similar_states)} similar states, "
        f"lookahead={lookahead_days}"
    )
    
    # Step 1: 计算所有样本的未来表现
    performances = compute_all_sample_performances(
        similar_states=similar_states,
        lookahead_days=lookahead_days,
        timeframe=timeframe,
    )
    
    if not performances:
        logger.warning("No valid future performance data computed")
        return []
    
    # Step 2: 对样本进行情景分类
    classified_performances = classify_all_samples(performances, lookahead_days)
    
    # Step 3: 聚合为情景摘要
    summaries = aggregate_scenarios(
        performances=classified_performances,
        lookahead_days=lookahead_days,
        include_sample_details=include_sample_details,
    )
    
    logger.info(
        f"Scenario analysis complete: {len(summaries)} scenarios, "
        f"{len(performances)} valid samples"
    )
    
    return summaries


def analyze_scenarios_for_symbol(
    symbol: str,
    timeframe: str = "1d",
    window_days: int = 30,
    top_k: int = 100,
    max_history_days: int = 365,
    lookahead_days: List[int] = DEFAULT_LOOKAHEAD_DAYS,
    include_sample_details: bool = False,
) -> Tuple[Optional[StateSnapshot], List[ScenarioSummary]]:
    """
    便捷函数：为指定 symbol 进行完整的情景分析
    
    Parameters
    ----------
    symbol : str
        目标币种
    timeframe : str
        时间粒度
    window_days : int
        快照窗口天数
    top_k : int
        相似样本数量
    max_history_days : int
        最大历史回溯天数
    lookahead_days : List[int]
        lookahead 窗口列表
    include_sample_details : bool
        是否包含样本详情
    
    Returns
    -------
    Tuple[StateSnapshot | None, List[ScenarioSummary]]
        (目标快照, 情景摘要列表)
    """
    from src.research.state_snapshot import compute_state_snapshot
    from src.research.similar_states import find_similar_states
    
    # 计算目标状态
    target = compute_state_snapshot(
        symbol=symbol,
        as_of=None,
        timeframe=timeframe,
        window_days=window_days,
    )
    
    if target is None:
        logger.warning(f"Failed to compute target snapshot for {symbol}")
        return None, []
    
    # 查找相似状态
    similar_states = find_similar_states(
        target=target,
        timeframe=timeframe,
        window_days=window_days,
        top_k=top_k,
        max_history_days=max_history_days,
        verbose=False,
    )
    
    if not similar_states:
        logger.warning(f"No similar states found for {symbol}")
        return target, []
    
    # 分析情景
    scenarios = analyze_scenarios(
        target=target,
        similar_states=similar_states,
        lookahead_days=lookahead_days,
        include_sample_details=include_sample_details,
    )
    
    return target, scenarios


if __name__ == "__main__":
    # 测试代码
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Testing Scenario Analysis Module")
    print("=" * 60)
    
    # 测试 ZEC 的情景分析
    target, scenarios = analyze_scenarios_for_symbol(
        symbol="ZEC",
        timeframe="1d",
        window_days=30,
        top_k=50,
        max_history_days=180,
        lookahead_days=[3, 7, 30],
        include_sample_details=False,
    )
    
    if target:
        print(f"\n=== Target Snapshot ===")
        print(f"Symbol: {target.symbol}")
        print(f"As of: {target.as_of}")
    
    if scenarios:
        print(f"\n=== Scenario Analysis Results ===")
        print(f"Total scenarios: {len(scenarios)}")
        
        for i, s in enumerate(scenarios):
            print(f"\n{i+1}. {s.label.upper()}")
            print(f"   Description: {s.description}")
            print(f"   Probability: {s.probability:.1%} ({s.sample_count} samples)")
            if s.avg_return_3d is not None:
                print(f"   Avg 3D Return: {s.avg_return_3d:.2%}")
            if s.avg_return_7d is not None:
                print(f"   Avg 7D Return: {s.avg_return_7d:.2%}")
            if s.avg_return_30d is not None:
                print(f"   Avg 30D Return: {s.avg_return_30d:.2%}")
            if s.max_drawdown_7d is not None:
                print(f"   Avg 7D Max DD: {s.max_drawdown_7d:.2%}")
    else:
        print("\nNo scenarios generated")
