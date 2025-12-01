from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, List
import pandas as pd
import logging

from src.data.db_storage import load_attention_data
from src.services.attention_service import AttentionService
from src.features.event_performance import compute_event_performance
from src.services.precomputation_service import PrecomputationService, DEFAULT_LOOKAHEAD_DAYS
from src.api.utils import validate_date_param
from src.api.schemas import Timeframe
from src.services.feature_service import FeatureService

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== 注意力数据 API ====================

@router.get("/api/attention", tags=["Attention"])
def get_attention_data(
    symbol: str = Query(default="ZEC", description="标的符号，如 ZEC"),
    granularity: Timeframe = Query(default=Timeframe.DAILY, description="时间粒度"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式"),
    columns: Optional[str] = Query(default=None, description="可选，逗号分隔的列白名单，仅返回指定存储列")
):
    """
    获取注意力时间序列数据
    """
    try:
        # Normalize inputs
        symbol = symbol.upper()
        # granularity is validated by Enum

        # 解析时间参数
        start_dt = validate_date_param(start, "start")
        end_dt = validate_date_param(end, "end")
        
        # 如果指定了列白名单，优先通过 FeatureService 只读所需存储列
        if columns:
            cols = [c.strip() for c in columns.split(',') if c.strip()]
            # timeframe 映射到 attention_features 的存储粒度
            tf_map = {"1d": "D", "4h": "4H"}
            att_tf = tf_map.get(granularity.value, "D")
            df = FeatureService.load_precomputed_features(
                symbol=symbol,
                start=start_dt,
                end=end_dt,
                timeframe=att_tf,
                columns=cols,
                fillna_zero=False,
                use_cache=True,
            )
        else:
            # 兼容默认行为：读取完整存储列（可能较多），保持现有响应结构
            # 注意：当前 load_attention_data 不区分粒度，默认日级
            df = load_attention_data(symbol, start_dt, end_dt)
        
        if df.empty:
            return []
        
        # 转换为 API 响应格式
        result = []
        if columns:
            # 仅返回请求的列（存在于存储中）
            for _, row in df.iterrows():
                dt = pd.to_datetime(row['datetime'])
                item: Dict[str, object] = {
                    "timestamp": int(dt.timestamp() * 1000),
                    "datetime": dt.isoformat(),
                }
                for c in cols:
                    if c in row:
                        val = row[c]
                        # 简单数值转换，保持非数值原样
                        try:
                            if pd.isna(val):
                                item[c] = 0
                            else:
                                item[c] = float(val) if isinstance(val, (int, float)) else val
                        except Exception:
                            item[c] = val
                result.append(item)
        else:
            for _, row in df.iterrows():
                dt = pd.to_datetime(row['datetime'])
                result.append({
                    "timestamp": int(dt.timestamp() * 1000),  # 转为毫秒
                    "datetime": dt.isoformat(),
                    "attention_score": float(row.get('attention_score', 0)),
                    "news_count": int(row.get('news_count', 0)),
                    "weighted_attention": float(row.get('weighted_attention', 0) or 0),
                    "bullish_attention": float(row.get('bullish_attention', 0) or 0),
                    "bearish_attention": float(row.get('bearish_attention', 0) or 0),
                    "event_intensity": int(row.get('event_intensity', 0) or 0),
                    "news_channel_score": float(row.get('news_channel_score', 0) or 0),
                    "google_trend_value": float(row.get('google_trend_value', 0) or 0),
                    "google_trend_zscore": float(row.get('google_trend_zscore', 0) or 0),
                    "google_trend_change_7d": float(row.get('google_trend_change_7d', 0) or 0),
                    "google_trend_change_30d": float(row.get('google_trend_change_30d', 0) or 0),
                    "twitter_volume": float(row.get('twitter_volume', 0) or 0),
                    "twitter_volume_zscore": float(row.get('twitter_volume_zscore', 0) or 0),
                    "twitter_volume_change_7d": float(row.get('twitter_volume_change_7d', 0) or 0),
                    "composite_attention_score": float(row.get('composite_attention_score', 0) or 0),
                    "composite_attention_zscore": float(row.get('composite_attention_zscore', 0) or 0),
                    "composite_attention_spike_flag": int(row.get('composite_attention_spike_flag', 0) or 0),
                })
        
        logger.info(f"Returned {len(result)} attention records for {symbol}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_attention_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 注意力事件 API ====================

@router.get("/api/attention-events", tags=["Attention"])
def get_attention_events(
    symbol: str = Query(default="ZEC"),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    lookback_days: int = Query(default=30),
    min_quantile: float = Query(default=0.8),
):
    try:
        start_dt = pd.to_datetime(start, utc=True) if start else None
        end_dt = pd.to_datetime(end, utc=True) if end else None
        events = AttentionService.get_attention_events(
            symbol=symbol, 
            start=start_dt, 
            end=end_dt, 
            lookback_days=lookback_days, 
            min_quantile=min_quantile
        )
        return [
            {
                "datetime": e.datetime.isoformat(),
                "event_type": e.event_type,
                "intensity": e.intensity,
                "summary": e.summary,
            } for e in events
        ]
    except Exception as e:
        logger.error(f"Error in get_attention_events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/attention-events/performance", tags=["Attention"])
def get_attention_event_performance(
    symbol: str = Query(default="ZEC"),
    lookahead_days: str = Query(default="1,3,5,10"),
):
    """按事件类型与前瞻窗口统计平均收益和样本数。

    lookahead_days: 逗号分隔的天数列表，例如 "1,3,5,10"。
    
    策略：
    - 如果 lookahead_days 等于默认值 [1,3,5,10]，优先读取缓存
    - 如果没有缓存，触发计算并存储
    - 如果参数非默认值，实时计算（不缓存）
    """
    try:
        symbol = symbol.upper()
        days = sorted([int(x) for x in lookahead_days.split(",") if x.strip()])
        
        # 检查是否使用默认参数（可以使用缓存）
        use_cache = (days == DEFAULT_LOOKAHEAD_DAYS)
        
        perf = None
        
        if use_cache:
            # 1. 尝试读取缓存
            perf = PrecomputationService.get_cached_event_performance(symbol)
            
            if perf:
                logger.debug(f"Using cached event_performance for {symbol}")
            else:
                # 2. 没有缓存，触发计算并存储
                logger.info(f"No cached event_performance for {symbol}, computing...")
                perf = PrecomputationService.compute_and_store_event_performance(
                    symbol=symbol, force_refresh=True
                )
        
        # 非默认参数或缓存计算失败，实时计算
        if not perf:
            perf = compute_event_performance(symbol=symbol, lookahead_days=days)
        
        # 转为可 JSON 化结构
        out: Dict[str, Dict[str, dict]] = {}
        for etype, per_h in perf.items():
            out[etype] = {}
            for h, p in per_h.items():
                out[etype][str(h)] = {
                    "event_type": p.event_type,
                    "lookahead_days": p.lookahead_days,
                    "avg_return": p.avg_return,
                    "sample_size": p.sample_size,
                }
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_attention_event_performance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
