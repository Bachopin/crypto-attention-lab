from fastapi import APIRouter, Body, HTTPException
from typing import Optional, List, Dict, Any
import pandas as pd
import logging

from src.backtest.basic_attention_factor import run_backtest_basic_attention
from src.backtest.strategy_templates import AttentionCondition
from src.backtest.attention_rotation import run_attention_rotation_backtest
from src.api.schemas import (
    BacktestParams, 
    MultiBacktestParams, 
    AttentionRotationParams
)

logger = logging.getLogger(__name__)

router = APIRouter()

def _parse_attention_condition(value) -> Optional[AttentionCondition]:
    if value is None:
        return None
    if isinstance(value, AttentionCondition):
        return value
    if not isinstance(value, dict):
        # If it's coming from Pydantic model, it might already be a dict or object
        # But here we handle the dict case primarily
        pass

    try:
        return AttentionCondition(
            source=value.get("source", "composite"),
            regime=value.get("regime", "high"),
            lower_quantile=value.get("lower_quantile"),
            upper_quantile=value.get("upper_quantile"),
            lookback_days=value.get("lookback_days", 30),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid attention_condition: {exc}") from None


# ==================== 基础回测 API ====================

@router.post("/api/backtest/basic-attention", tags=["Backtest"])
def backtest_basic_attention(
    params: BacktestParams = Body(...)
):
    """单币种基础注意力策略回测"""
    try:
        start_dt = pd.to_datetime(params.start, utc=True) if params.start else None
        end_dt = pd.to_datetime(params.end, utc=True) if params.end else None
        
        attention_condition = _parse_attention_condition(params.attention_condition)
        
        res = run_backtest_basic_attention(
            symbol=params.symbol,
            lookback_days=params.lookback_days,
            attention_quantile=params.attention_quantile,
            max_daily_return=params.max_daily_return,
            holding_days=params.holding_days,
            stop_loss_pct=params.stop_loss_pct,
            take_profit_pct=params.take_profit_pct,
            max_holding_days=params.max_holding_days,
            position_size=params.position_size,
            start=start_dt,
            end=end_dt,
            attention_source=params.attention_source,
            attention_condition=attention_condition,
        )
        # 为了与前端类型对齐，补充 params 字段（后端本来未返回）
        try:
            out = dict(res)
            out.setdefault("params", {
                "symbol": params.symbol,
                "lookback_days": params.lookback_days,
                "attention_quantile": params.attention_quantile,
                "max_daily_return": params.max_daily_return,
                "holding_days": params.holding_days,
                "stop_loss_pct": params.stop_loss_pct,
                "take_profit_pct": params.take_profit_pct,
                "max_holding_days": params.max_holding_days,
                "position_size": params.position_size,
                "attention_source": params.attention_source,
                "start": params.start,
                "end": params.end,
            })
            return out
        except Exception:
            # 兜底返回原始结构
            return res
    except Exception as e:
        logger.error(f"Error in backtest_basic_attention: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/backtest/basic-attention/multi", tags=["Backtest"])
def backtest_basic_attention_multi(
    params: MultiBacktestParams = Body(...)
):
    """多币种基础注意力策略回测"""
    try:
        start_dt = pd.to_datetime(params.start, utc=True) if params.start else None
        end_dt = pd.to_datetime(params.end, utc=True) if params.end else None
        
        attention_condition = _parse_attention_condition(params.attention_condition)

        per_symbol_summary = {}
        per_symbol_equity_curves = {}
        per_symbol_trades = {}
        per_symbol_meta = {}

        for sym in params.symbols:
            res = run_backtest_basic_attention(
                symbol=sym,
                lookback_days=params.lookback_days,
                attention_quantile=params.attention_quantile,
                max_daily_return=params.max_daily_return,
                holding_days=params.holding_days,
                stop_loss_pct=params.stop_loss_pct,
                take_profit_pct=params.take_profit_pct,
                max_holding_days=params.max_holding_days,
                position_size=params.position_size,
                start=start_dt,
                end=end_dt,
                attention_source=params.attention_source,
                attention_condition=attention_condition,
            )
            if "summary" in res and "equity_curve" in res:
                per_symbol_summary[sym] = res["summary"]
                per_symbol_equity_curves[sym] = res["equity_curve"]
                per_symbol_trades[sym] = res.get("trades", [])
                per_symbol_meta[sym] = res.get("meta", {})
            else:
                per_symbol_summary[sym] = {"error": res.get("error", "unknown error")}
                per_symbol_equity_curves[sym] = []
                per_symbol_trades[sym] = []
                per_symbol_meta[sym] = res.get("meta", {})

        # Placeholder for aggregate summary (to be implemented)
        aggregate_summary = {
            "total_return": 0.0,
            "cumulative_return": 0.0,
            "annualized_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "sharpe_ratio": 0.0,
            "avg_return": 0.0,
            "avg_trade_return": 0.0,
        }
        
        aggregate_equity_curve = []

        # 前端期望存在 params 字段（至少包含 symbols），否则会在转换时读取 undefined.params.symbols 报错
        response = {
            "params": {
                "symbols": params.symbols,
                "lookback_days": params.lookback_days,
                "attention_quantile": params.attention_quantile,
                "max_daily_return": params.max_daily_return,
                "holding_days": params.holding_days,
                "stop_loss_pct": params.stop_loss_pct,
                "take_profit_pct": params.take_profit_pct,
                "max_holding_days": params.max_holding_days,
                "position_size": params.position_size,
                "attention_source": params.attention_source,
                "start": params.start,
                "end": params.end,
            },
            "per_symbol_summary": per_symbol_summary,
            "per_symbol_equity_curves": per_symbol_equity_curves,
            "per_symbol_trades": per_symbol_trades,
            "per_symbol_meta": per_symbol_meta,
            "aggregate_summary": aggregate_summary,
            "aggregate_equity_curve": aggregate_equity_curve,
            "meta": {
                "attention_source": params.attention_source,
                "symbols": params.symbols,
            },
        }
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backtest_basic_attention_multi: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 注意力轮动策略回测 API ====================

@router.post("/api/backtest/attention-rotation", tags=["Backtest"])
def backtest_attention_rotation(params: AttentionRotationParams = Body(...)):
    """
    多币种 Attention 轮动策略回测
    """
    try:
        start_dt = pd.to_datetime(params.start, utc=True) if params.start else None
        end_dt = pd.to_datetime(params.end, utc=True) if params.end else None

        result = run_attention_rotation_backtest(
            symbols=params.symbols,
            attention_source=params.attention_source,
            rebalance_days=params.rebalance_days,
            lookback_days=params.lookback_days,
            top_k=params.top_k,
            start=start_dt,
            end=end_dt,
        )
        
        if "error" in result:
             raise HTTPException(status_code=400, detail=result["error"])
             
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backtest_attention_rotation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
