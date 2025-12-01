from fastapi import APIRouter, Body, Query, HTTPException
from typing import Optional, List, Dict, Any
import pandas as pd
import logging
from datetime import datetime, timezone

from src.research.attention_regimes import analyze_attention_regimes
from src.research.state_snapshot import compute_state_snapshot, compute_state_snapshots_batch
from src.research.similar_states import find_similar_states
from src.research.scenarios import analyze_scenarios
from src.features.node_influence import load_node_carry_factors
from src.data.db_storage import get_available_symbols
from src.services.precomputation_service import PrecomputationService, DEFAULT_SNAPSHOT_WINDOW
from src.api.schemas import (
    Timeframe, 
    AttentionRegimeParams, 
    StateSnapshotBatchParams, 
    SimilarCasesCustomParams, 
    ScenarioAnalysisCustomParams
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== Research: Attention Regimes ====================

@router.post("/api/research/attention-regimes", tags=["Research"])
def research_attention_regimes(params: AttentionRegimeParams = Body(...)):
    """多币种 attention regime 研究分析接口"""
    
    normalized_symbols = [s.upper() for s in params.symbols if s.strip()]
    if not normalized_symbols:
        raise HTTPException(status_code=400, detail="symbols must contain at least one valid entry")

    try:
        start_dt = pd.to_datetime(params.start, utc=True) if params.start else None
        end_dt = pd.to_datetime(params.end, utc=True) if params.end else None

        result = analyze_attention_regimes(
            symbols=normalized_symbols,
            lookahead_days=params.lookahead_days,
            attention_source=params.attention_source.value,
            split_method=params.split_method,
            split_quantiles=params.split_quantiles,
            start=start_dt,
            end=end_dt,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        logger.error("Error in research_attention_regimes", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ==================== State Snapshot API ====================

@router.get("/api/state/snapshot", tags=["Research"])
def get_state_snapshot(
    symbol: str = Query(..., description="标的符号，如 ZEC, BTC"),
    timeframe: Timeframe = Query(Timeframe.DAILY, description="时间粒度"),
    window_days: int = Query(30, ge=7, le=365, description="特征计算窗口天数"),
):
    """
    获取指定 symbol 当前的状态快照
    
    策略：
    - 如果 window_days=30（默认值），优先读取缓存
    - 如果没有缓存，触发计算并存储
    - 如果参数非默认值，实时计算（不缓存）
    """
    try:
        # Normalize symbol
        symbol = symbol.upper()
        tf_value = timeframe.value
        
        # 检查是否使用默认参数（可以使用缓存）
        use_cache = (window_days == DEFAULT_SNAPSHOT_WINDOW)
        
        result = None
        
        if use_cache:
            # 1. 尝试读取最新缓存
            as_of = datetime.now(timezone.utc)
            cached = PrecomputationService.get_cached_state_snapshot(
                symbol=symbol,
                as_of=as_of,
                timeframe=tf_value,
            )
            
            if cached:
                logger.debug(f"Using cached state_snapshot for {symbol} ({tf_value})")
                result = cached
            else:
                # 2. 没有缓存，触发计算并存储
                logger.info(f"No cached state_snapshot for {symbol} ({tf_value}), computing...")
                count = PrecomputationService.compute_and_store_state_snapshots(
                    symbol=symbol,
                    timeframe=tf_value,
                    force_full=False,  # 增量更新
                )
                
                if count > 0:
                    # 重新读取缓存
                    cached = PrecomputationService.get_cached_state_snapshot(
                        symbol=symbol,
                        as_of=as_of,
                        timeframe=tf_value,
                    )
                    if cached:
                        result = cached
        
        # 非默认参数或缓存计算失败，实时计算
        if not result:
            snapshot = compute_state_snapshot(
                symbol=symbol,
                as_of=None,  # 使用当前时间
                timeframe=tf_value,
                window_days=window_days,
            )
            
            if snapshot is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"No data available for symbol {symbol}. "
                           f"Please ensure price and attention data exist for this symbol."
                )
            
            result = snapshot.to_dict()
        
        logger.info(
            f"State snapshot returned for {symbol}: "
            f"{len(result.get('features', {}))} features, {len(result.get('raw_stats', {}))} raw stats"
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_state_snapshot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/state/snapshot/batch", tags=["Research"])
def get_state_snapshots_batch(
    params: StateSnapshotBatchParams = Body(...)
):
    """
    批量获取多个 symbol 的状态快照
    """
    try:
        # 尝试优先使用预计算缓存（仅在使用默认 window_days 时）
        result_snapshots = {}
        success_count = 0
        failed_count = 0

        use_cache = (params.window_days == DEFAULT_SNAPSHOT_WINDOW)

        # 如果可使用缓存，按 symbol 尝试读取缓存快照；对未命中的 symbol 再批量计算
        if use_cache:
            from datetime import datetime, timezone
            as_of = datetime.now(timezone.utc)
            missing: list[str] = []

            for symbol in params.symbols:
                try:
                    cached = PrecomputationService.get_cached_state_snapshot(
                        symbol=symbol,
                        as_of=as_of,
                        timeframe=params.timeframe.value,
                    )
                    if cached:
                        result_snapshots[symbol] = cached
                        success_count += 1
                    else:
                        # 标记为需实时计算
                        missing.append(symbol)
                except Exception:
                    # 读取缓存失败，退回到实时计算
                    missing.append(symbol)

            # 对未命中的 symbol 执行原有的批量计算（仅针对缺失项）
            if missing:
                computed = compute_state_snapshots_batch(
                    symbols=missing,
                    as_of=None,
                    timeframe=params.timeframe.value,
                    window_days=params.window_days,
                )
                for symbol, snapshot in computed.items():
                    if snapshot is not None:
                        result_snapshots[symbol] = snapshot.to_dict()
                        success_count += 1
                    else:
                        result_snapshots[symbol] = None
                        failed_count += 1
        else:
            # 批量计算（不使用缓存）
            snapshots = compute_state_snapshots_batch(
                symbols=params.symbols,
                as_of=None,
                timeframe=params.timeframe.value,
                window_days=params.window_days,
            )

            for symbol, snapshot in snapshots.items():
                if snapshot is not None:
                    result_snapshots[symbol] = snapshot.to_dict()
                    success_count += 1
                else:
                    result_snapshots[symbol] = None
                    failed_count += 1
        
        return {
            "snapshots": result_snapshots,
            "meta": {
                "requested": len(params.symbols),
                "success": success_count,
                "failed": failed_count,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_state_snapshots_batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Similar States API ====================

@router.get("/api/state/similar-cases", tags=["Research"])
def get_similar_cases(
    symbol: str = Query(..., description="目标币种符号，如 ZEC, BTC"),
    timeframe: Timeframe = Query(Timeframe.DAILY, description="时间粒度"),
    window_days: int = Query(30, ge=7, le=365, description="特征计算窗口天数"),
    top_k: int = Query(50, ge=1, le=500, description="返回的相似样本数量"),
    max_history_days: int = Query(365, ge=30, le=1095, description="最大历史回溯天数"),
    include_same_symbol: bool = Query(True, description="是否包含相同币种的历史状态"),
):
    """
    获取当前 symbol 在给定 timeframe/window_days 下的相似历史状态样本列表。
    """
    try:
        symbol = symbol.upper()
        
        # 计算目标状态快照
        target = compute_state_snapshot(
            symbol=symbol,
            as_of=None,  # 使用当前时间
            timeframe=timeframe.value,
            window_days=window_days,
        )
        
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for symbol {symbol}. "
                       f"Please ensure price and attention data exist for this symbol."
            )
        
        # 获取候选币种列表
        candidate_symbols = get_available_symbols()
        
        if not candidate_symbols:
            return {
                "target": target.to_dict(),
                "similar_cases": [],
                "meta": {
                    "total_candidates_processed": 0,
                    "results_returned": 0,
                    "message": "No candidate symbols available in database"
                }
            }
        
        # 查找相似状态
        similar_states = find_similar_states(
            target=target,
            candidate_symbols=candidate_symbols,
            timeframe=timeframe.value,
            window_days=window_days,
            top_k=top_k,
            max_history_days=max_history_days,
            include_same_symbol=include_same_symbol,
            verbose=False,
        )
        
        # 转换结果
        similar_cases = [state.to_dict() for state in similar_states]
        
        # 计算实际处理的候选数量（近似值）
        approx_candidates = len(candidate_symbols) * min(max_history_days, 365)
        
        message = f"Found {len(similar_cases)} similar historical states"
        if len(similar_cases) == 0:
            message = "No similar states found. Try increasing max_history_days or relaxing filters."
        
        logger.info(
            f"Similar cases returned for {symbol}: {len(similar_cases)} results "
            f"(top_k={top_k}, history={max_history_days}d)"
        )
        
        return {
            "target": target.to_dict(),
            "similar_cases": similar_cases,
            "meta": {
                "total_candidates_processed": approx_candidates,
                "results_returned": len(similar_cases),
                "message": message
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_similar_cases: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/state/similar-cases/custom", tags=["Research"])
def get_similar_cases_custom(
    params: SimilarCasesCustomParams = Body(...)
):
    """
    自定义参数的相似状态检索（高级用法）
    """
    try:
        # 候选币种
        candidate_symbols = params.candidate_symbols
        if not candidate_symbols:
            candidate_symbols = get_available_symbols()
        
        # 计算目标状态
        target = compute_state_snapshot(
            symbol=params.symbol,
            as_of=None,
            timeframe=params.timeframe.value,
            window_days=params.window_days,
        )
        
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for symbol {params.symbol}"
            )
        
        # 查找相似状态
        similar_states = find_similar_states(
            target=target,
            candidate_symbols=candidate_symbols,
            timeframe=params.timeframe.value,
            window_days=params.window_days,
            top_k=params.top_k,
            max_history_days=params.max_history_days,
            exclusion_days=params.exclusion_days,
            distance_metric=params.distance_metric,
            include_same_symbol=params.include_same_symbol,
            verbose=False,
        )
        
        # 转换结果
        similar_cases = [state.to_dict() for state in similar_states]
        
        return {
            "target": target.to_dict(),
            "similar_cases": similar_cases,
            "meta": {
                "results_returned": len(similar_cases),
                "distance_metric": params.distance_metric,
                "candidate_symbols_count": len(candidate_symbols),
                "message": f"Found {len(similar_cases)} similar states using {params.distance_metric} distance"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_similar_cases_custom: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Scenario Analysis API ====================

@router.get("/api/state/scenarios", tags=["Research"])
def get_state_scenarios(
    symbol: str = Query(..., description="目标币种符号，如 ZEC, BTC"),
    timeframe: Timeframe = Query(Timeframe.DAILY, description="时间粒度"),
    window_days: int = Query(30, ge=7, le=365, description="特征计算窗口天数"),
    top_k: int = Query(100, ge=10, le=500, description="用于分析的相似样本数量"),
    max_history_days: int = Query(365, ge=30, le=1095, description="最大历史回溯天数"),
    include_sample_details: bool = Query(False, description="是否包含样本详情"),
):
    """
    对当前 symbol 的状态进行基于 Attention 的未来情景分析。
    """
    try:
        symbol = symbol.upper()
        
        # Step 1: 计算目标状态快照
        target = compute_state_snapshot(
            symbol=symbol,
            as_of=None,
            timeframe=timeframe.value,
            window_days=window_days,
        )
        
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for symbol {symbol}. "
                       f"Please ensure price and attention data exist for this symbol."
            )
        
        # Step 2: 查找相似状态
        candidate_symbols = get_available_symbols()
        
        if not candidate_symbols:
            return {
                "target": target.to_dict(),
                "scenarios": [],
                "meta": {
                    "total_similar_samples": 0,
                    "valid_samples_analyzed": 0,
                    "lookahead_days": [3, 7, 30],
                    "message": "No candidate symbols available in database"
                }
            }
        
        try:
            similar_states = find_similar_states(
                target=target,
                candidate_symbols=candidate_symbols,
                timeframe=timeframe.value,
                window_days=window_days,
                top_k=top_k,
                max_history_days=max_history_days,
                include_same_symbol=True,
                verbose=False,
            )
        except Exception as e:
            logger.error(f"Error finding similar states for {symbol}: {e}", exc_info=True)
            similar_states = []
        
        if not similar_states:
            return {
                "target": target.to_dict(),
                "scenarios": [],
                "meta": {
                    "total_similar_samples": 0,
                    "valid_samples_analyzed": 0,
                    "lookahead_days": [3, 7, 30],
                    "message": "No similar historical states found"
                }
            }
        
        # Step 3: 分析情景
        lookahead_days = [3, 7, 30]
        scenarios = analyze_scenarios(
            target=target,
            similar_states=similar_states,
            lookahead_days=lookahead_days,
            include_sample_details=include_sample_details,
        )
        
        # 计算有效样本数
        valid_samples = sum(s.sample_count for s in scenarios)
        
        # 转换结果
        scenarios_data = [s.to_dict() for s in scenarios]
        
        logger.info(
            f"Scenario analysis completed for {symbol}: "
            f"{len(scenarios)} scenarios from {valid_samples} valid samples"
        )
        
        return {
            "target": target.to_dict(),
            "scenarios": scenarios_data,
            "meta": {
                "total_similar_samples": len(similar_states),
                "valid_samples_analyzed": valid_samples,
                "lookahead_days": lookahead_days,
                "message": f"Scenario analysis complete: {len(scenarios)} scenarios identified"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_state_scenarios: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/state/scenarios/custom", tags=["Research"])
def get_state_scenarios_custom(
    params: ScenarioAnalysisCustomParams = Body(...)
):
    """
    自定义参数的情景分析（高级用法）
    """
    try:
        # 候选币种
        candidate_symbols = params.candidate_symbols
        if not candidate_symbols:
            candidate_symbols = get_available_symbols()
        
        # Step 1: 计算目标状态
        target = compute_state_snapshot(
            symbol=params.symbol,
            as_of=None,
            timeframe=params.timeframe.value,
            window_days=params.window_days,
        )
        
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for symbol {params.symbol}"
            )
        
        # Step 2: 查找相似状态
        try:
            similar_states = find_similar_states(
                target=target,
                candidate_symbols=candidate_symbols,
                timeframe=params.timeframe.value,
                window_days=params.window_days,
                top_k=params.top_k,
                max_history_days=params.max_history_days,
                include_same_symbol=True,
                verbose=False,
            )
        except Exception as e:
            logger.error(f"Error finding similar states (custom) for {params.symbol}: {e}", exc_info=True)
            similar_states = []
        
        if not similar_states:
            return {
                "target": target.to_dict(),
                "scenarios": [],
                "meta": {
                    "total_similar_samples": 0,
                    "valid_samples_analyzed": 0,
                    "lookahead_days": params.lookahead_days,
                    "message": "No similar historical states found"
                }
            }
        
        # Step 3: 分析情景
        scenarios = analyze_scenarios(
            target=target,
            similar_states=similar_states,
            lookahead_days=params.lookahead_days,
            include_sample_details=params.include_sample_details,
        )
        
        valid_samples = sum(s.sample_count for s in scenarios)
        scenarios_data = [s.to_dict() for s in scenarios]
        
        return {
            "target": target.to_dict(),
            "scenarios": scenarios_data,
            "meta": {
                "total_similar_samples": len(similar_states),
                "valid_samples_analyzed": valid_samples,
                "lookahead_days": params.lookahead_days,
                "candidate_symbols_count": len(candidate_symbols),
                "message": f"Custom scenario analysis complete: {len(scenarios)} scenarios identified"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_state_scenarios_custom: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 节点带货能力 API ====================

@router.get("/api/node-influence", tags=["Research"])
def get_node_influence(
    symbol: Optional[str] = Query(None, description="标的符号，如 ZEC，留空返回所有"),
    min_events: int = Query(10, ge=1, description="最小事件样本数过滤"),
    sort_by: str = Query("ir", description="排序字段: ir | mean_excess_return | hit_rate"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数量上限"),
):
    """查询节点带货能力因子。"""

    try:
        # Normalize sort_by
        sort_by = sort_by.lower()

        df = load_node_carry_factors(symbol)
        if df.empty:
            return []

        # 过滤样本数
        if "n_events" in df.columns:
            df = df[df["n_events"] >= int(min_events)]
        if df.empty:
            return []

        # 排序
        valid_sort = {"ir", "mean_excess_return", "hit_rate"}
        if sort_by not in valid_sort:
            sort_by = "ir"
        if sort_by in df.columns:
            df = df.sort_values(by=sort_by, ascending=False)

        df = df.head(limit)

        result = []
        for _, row in df.iterrows():
            result.append({
                "symbol": str(row.get("symbol")),
                "node_id": str(row.get("node_id")),
                "n_events": int(row.get("n_events", 0)),
                "mean_excess_return": float(row.get("mean_excess_return", 0.0)),
                "hit_rate": float(row.get("hit_rate", 0.0)),
                "ir": float(row.get("ir", 0.0)),
                "lookahead": str(row.get("lookahead", "1d")),
                "lookback_days": int(row.get("lookback_days", 365)),
            })

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_node_influence: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
