from fastapi import APIRouter, Body, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import pandas as pd
import logging

from src.backtest.basic_attention_factor import run_backtest_basic_attention
from src.backtest.strategy_templates import AttentionCondition
from src.backtest.attention_rotation import run_attention_rotation_backtest

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== Models ====================

class BacktestParams(BaseModel):
    """基础回测参数模型"""
    symbol: str = Field(..., description="交易对符号")
    lookback_days: int = Field(30, ge=1, description="回溯天数")
    attention_quantile: float = Field(0.8, ge=0.0, le=1.0, description="注意力分位数阈值")
    max_daily_return: float = Field(0.05, description="最大日涨幅限制")
    holding_days: int = Field(3, ge=1, description="持仓天数")
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_holding_days: Optional[int] = None
    position_size: float = Field(1.0, gt=0.0, le=1.0)
    start: Optional[str] = None
    end: Optional[str] = None
    attention_condition: Optional[Dict[str, Any]] = None
    attention_source: str = Field("legacy", pattern="^(legacy|composite)$")

class MultiBacktestParams(BacktestParams):
    """多币种回测参数模型"""
    symbol: Optional[str] = None # 覆盖父类，使其可选
    symbols: List[str] = Field(..., min_length=1, description="交易对列表")


def _parse_attention_condition(value) -> Optional[AttentionCondition]:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="attention_condition must be an object")

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
                per_symbol_meta[sym] = res.get("meta", {})
            else:
                per_symbol_summary[sym] = {"error": res.get("error", "unknown error")}
                per_symbol_equity_curves[sym] = []
                per_symbol_meta[sym] = res.get("meta", {})

        return {
            "per_symbol_summary": per_symbol_summary,
            "per_symbol_equity_curves": per_symbol_equity_curves,
            "per_symbol_meta": per_symbol_meta,
            "meta": {
                "attention_source": params.attention_source,
                "symbols": params.symbols,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backtest_basic_attention_multi: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 注意力轮动策略回测 API ====================

@router.post("/api/backtest/attention-rotation", tags=["Backtest"])
def backtest_attention_rotation(payload: dict = Body(...)):
    """
    多币种 Attention 轮动策略回测
    """
    try:
        symbols = payload.get("symbols") or []
        if not symbols or not isinstance(symbols, list):
            raise HTTPException(status_code=400, detail="symbols must be a non-empty list")

        attention_source = payload.get("attention_source", "composite")
        rebalance_days = int(payload.get("rebalance_days", 7))
        lookback_days = int(payload.get("lookback_days", 30))
        top_k = int(payload.get("top_k", 3))

        start = payload.get("start")
        end = payload.get("end")
        start_dt = pd.to_datetime(start, utc=True) if start else None
        end_dt = pd.to_datetime(end, utc=True) if end else None

        result = run_attention_rotation_backtest(
            symbols=symbols,
            attention_source=attention_source,
            rebalance_days=rebalance_days,
            lookback_days=lookback_days,
            top_k=top_k,
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
