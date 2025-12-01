from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
import pandas as pd
import logging
import requests as http_requests
import time
from datetime import datetime

from src.data.db_storage import (
    load_price_data,
    load_news_data,
    get_available_symbols,
    get_db,
)
from src.database.models import Symbol, get_session
from src.api.utils import validate_date_param
from src.api.schemas import Timeframe

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== 价格数据 API ====================

@router.get("/api/price", tags=["Market Data"])
def get_price_data(
    symbol: str = Query(default="ZECUSDT", description="交易对符号，如 ZECUSDT"),
    timeframe: Timeframe = Query(default=Timeframe.DAILY, description="时间周期"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式"),
    limit: Optional[int] = Query(default=None, description="返回最近 N 条 K 线，从最新向前取")
):
    """
    获取价格 OHLCV 数据
    """
    try:
        # Normalize inputs
        symbol = symbol.upper()
        # timeframe is already validated by Enum

        # 解析时间参数
        start_dt = validate_date_param(start, "start")
        end_dt = validate_date_param(end, "end")
        
        # 加载数据（直接从数据库）
        df, is_fallback = load_price_data(symbol, timeframe.value, start_dt, end_dt)
        
        if df.empty:
            return []
        
        # 应用 limit：取最近 N 条（从最新向前）
        if limit is not None and limit > 0:
            df = df.tail(limit)
        
        # 转换为 API 响应格式
        result = []
        for _, row in df.iterrows():
            # 确保 datetime 是 pandas Timestamp
            dt = pd.to_datetime(row['datetime'])
            
            result.append({
                "timestamp": int(dt.timestamp() * 1000),  # 转为毫秒
                "datetime": dt.isoformat(),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row.get('volume', 0))
            })
        
        logger.info(f"Returned {len(result)} price records for {symbol} {timeframe.value}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_price_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 新闻数据 API ====================

@router.get("/api/news", tags=["Market Data"])
def get_news_data(
    symbol: str = Query(default="ALL", description="标的符号，如 ZEC，或 ALL 获取所有"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式"),
    limit: Optional[int] = Query(default=None, description="返回的最大条数，用于分页"),
    before: Optional[str] = Query(default=None, description="返回该时间之前的新闻（ISO8601），用于游标分页"),
    source: Optional[str] = Query(default=None, description="按新闻源过滤，如 coindesk")
):
    """
    获取新闻列表
    """
    try:
        # 解析时间参数
        start_dt = validate_date_param(start, "start")
        end_dt = validate_date_param(end, "end")
        
        # 若提供 before，则将 end_dt 覆盖为 before 并可选设置默认窗口
        if before:
            before_dt = validate_date_param(before, "before")
            end_dt = before_dt if before_dt else end_dt

        # 加载新闻数据
        df = load_news_data(symbol, start_dt, end_dt, limit)

        # 按来源过滤（可选）
        if source and not df.empty and 'source' in df.columns:
            df = df[df['source'] == source]

        # 按时间倒序（最新在前）
        if not df.empty and 'datetime' in df.columns:
            df = df.sort_values(by='datetime', ascending=False)

        # 应用 limit（若提供）
        if limit is not None and limit > 0:
            df = df.head(limit)
        
        if df.empty:
            return []
        
        # 转换为 API 响应格式
        result = []
        for _, row in df.iterrows():
            dt = pd.to_datetime(row['datetime'])
            
            result.append({
                "datetime": dt.isoformat() if pd.notna(dt) else None,
                "source": str(row.get('source', 'Unknown')),
                "title": str(row.get('title', '')),
                "url": str(row.get('url', '')),
                "relevance": str(row.get('relevance', '')),
                "source_weight": float(row.get('source_weight', 0) or 0),
                "sentiment_score": float(row.get('sentiment_score', 0) or 0),
                "tags": str(row.get('tags', '')),
                "symbols": str(row.get('symbols', '')),
                "language": str(row.get('language', '')),
            })
        
        logger.info(f"Returned {len(result)} news items for {symbol}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_news_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/news/count", tags=["Market Data"])
def get_news_count(
    symbol: str = Query(default="ALL", description="标的符号，如 ZEC，或 ALL 获取所有"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式"),
    before: Optional[str] = Query(default=None, description="返回该时间之前的新闻（ISO8601），用于游标分页"),
    source: Optional[str] = Query(default=None, description="按新闻源过滤")
):
    """
    获取新闻条目总数（用于分页展示）。
    
    优化：对于无过滤条件的全局查询，使用预计算缓存，响应时间 <10ms。
    """
    try:
        # 快速路径：无过滤条件时直接返回缓存的总数
        if symbol.upper() == "ALL" and not start and not end and not before and not source:
            db = get_db()
            total = db.get_news_total_count()
            return {"total": total, "cached": True}
        
        # 有过滤条件时，使用传统查询
        start_dt = None
        end_dt = None
        
        if start:
            try:
                start_dt = pd.to_datetime(start, utc=True)
                if start_dt.year < 2009:
                    raise ValueError(f"Start time {start_dt} is too early (before 2009)")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
                if end_dt.year < 2009:
                    raise ValueError(f"End time {end_dt} is too early (before 2009)")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        if before:
            try:
                before_dt = pd.to_datetime(before, utc=True)
                if before_dt.year < 2009:
                    raise ValueError(f"Before time {before_dt} is too early (before 2009)")
                end_dt = before_dt if before_dt else end_dt
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid before time format: {e}")

        df = load_news_data(symbol, start_dt, end_dt)
        if source and not df.empty and 'source' in df.columns:
            df = df[df['source'] == source]

        return {"total": int(len(df)), "cached": False}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_news_count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/news/stats/hourly", tags=["Market Data"])
def get_news_hourly_stats(
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式"),
    limit: int = Query(default=168, description="返回最近 N 个小时的统计，默认 168（7天）")
):
    """
    获取每小时新闻数量统计。
    
    返回格式: [{"period": "2025-12-01T14", "count": 10}, ...]
    """
    try:
        start_dt = None
        end_dt = None
        
        if start:
            start_dt = pd.to_datetime(start, utc=True)
        if end:
            end_dt = pd.to_datetime(end, utc=True)
        
        db = get_db()
        stats = db.get_news_hourly_stats(start_dt, end_dt, limit)
        
        return {"stats": stats, "count": len(stats)}
    
    except Exception as e:
        logger.error(f"Error in get_news_hourly_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/news/stats/daily", tags=["Market Data"])
def get_news_daily_stats(
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式"),
    limit: int = Query(default=30, description="返回最近 N 天的统计，默认 30")
):
    """
    获取每日新闻数量统计。
    
    返回格式: [{"period": "2025-12-01", "count": 150}, ...]
    """
    try:
        start_dt = None
        end_dt = None
        
        if start:
            start_dt = pd.to_datetime(start, utc=True)
        if end:
            end_dt = pd.to_datetime(end, utc=True)
        
        db = get_db()
        stats = db.get_news_daily_stats(start_dt, end_dt, limit)
        
        return {"stats": stats, "count": len(stats)}
    
    except Exception as e:
        logger.error(f"Error in get_news_daily_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/news/stats/rebuild", tags=["Management"])
def rebuild_news_stats():
    """
    重建所有新闻统计缓存（管理接口）。
    
    用于初始化或修复统计数据。
    """
    try:
        db = get_db()
        db.rebuild_all_news_stats()
        return {"success": True, "message": "News stats rebuilt successfully"}
    except Exception as e:
        logger.error(f"Error rebuilding news stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/news/trend", tags=["Market Data"])
def get_news_trend(
    symbol: str = Query(default="ALL", description="标的符号，如 ZEC，或 ALL 获取所有"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式"),
    interval: str = Query(default="1d", description="聚合间隔: 1h（小时）或 1d（天）")
):
    """
    获取新闻趋势聚合数据 - 按时间间隔统计新闻数量和注意力
    """
    try:
        # Normalize interval
        interval = interval.lower()

        start_dt = None
        end_dt = None
        
        if start:
            try:
                start_dt = pd.to_datetime(start, utc=True)
                if start_dt.year < 2009:
                    raise ValueError(f"Start time {start_dt} is too early")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        # 加载新闻数据（无 limit，获取全部）
        df = load_news_data(symbol, start_dt, end_dt, limit=None)
        
        if df.empty:
            return []
        
        # 确保 datetime 列为 datetime 类型
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        
        # 按时间间隔分组
        if interval == '1h':
            df['time_bucket'] = df['datetime'].dt.floor('h')
            time_format = '%Y-%m-%dT%H:00:00Z'
        else:  # 默认按天
            df['time_bucket'] = df['datetime'].dt.floor('D')
            time_format = '%Y-%m-%d'
        
        # 确保 source_weight 和 sentiment_score 为数值
        df['source_weight'] = pd.to_numeric(df.get('source_weight', 1), errors='coerce').fillna(1)
        df['sentiment_score'] = pd.to_numeric(df.get('sentiment_score', 0), errors='coerce').fillna(0)
        
        # 聚合统计
        agg_df = df.groupby('time_bucket').agg(
            count=('datetime', 'count'),
            attention=('source_weight', 'sum'),
            avg_sentiment=('sentiment_score', 'mean')
        ).reset_index()
        
        # 排序
        agg_df = agg_df.sort_values('time_bucket')
        
        # 计算 Z-Score 并转换为 0-100 分数
        # 使用全量数据的均值和标准差（更稳定）
        mean_attention = agg_df['attention'].mean()
        std_attention = agg_df['attention'].std()
        
        # 避免除零
        if std_attention == 0 or pd.isna(std_attention):
            std_attention = 1
        
        # Z-Score 转换为 0-100 分数
        # Z=0 → 50分, Z=2 → 80分, Z=-2 → 20分
        agg_df['z_score'] = (agg_df['attention'] - mean_attention) / std_attention
        agg_df['attention_score'] = (50 + agg_df['z_score'] * 15).clip(0, 100)
        
        # 转换为结果列表
        result = []
        for _, row in agg_df.iterrows():
            result.append({
                "time": row['time_bucket'].strftime(time_format),
                "count": int(row['count']),
                "attention": round(float(row['attention']), 2),
                "attention_score": round(float(row['attention_score']), 1),
                "z_score": round(float(row['z_score']), 2),
                "avg_sentiment": round(float(row['avg_sentiment']), 4)
            })
        
        logger.info(f"Returned {len(result)} trend data points for {symbol}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_news_trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 币种列表 API ====================

@router.get("/api/symbols", tags=["Market Data"])
def get_symbols():
    """
    获取正在自动更新的币种列表（用于代币看板选择）
    """
    try:
        # 只返回正在自动更新的代币
        session = get_session()
        symbols = [s.symbol for s in session.query(Symbol).filter(
            Symbol.auto_update_price == True
        ).order_by(Symbol.symbol).all()]
        session.close()
        
        # 如果没有自动更新的代币，返回默认列表
        if not symbols:
            symbols = get_available_symbols()
        
        return {
            "symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CoinGecko 市值排行 API ====================

# 缓存 CoinGecko 市值前100数据（每小时更新一次）
_top_coins_cache = {
    "data": [],
    "timestamp": 0,
    "ttl": 3600  # 1 hour cache
}

@router.get("/api/top-coins", tags=["Market Data"])
def get_top_coins(
    limit: int = Query(100, ge=1, le=250, description="返回的币种数量，最大250"),
    vs_currency: str = Query("usd", description="计价货币")
):
    """
    获取 CoinGecko 市值排名前 N 的币种列表
    """
    global _top_coins_cache
    
    try:
        # Normalize vs_currency
        vs_currency = vs_currency.lower()

        now = time.time()
        
        # 检查缓存是否有效
        if _top_coins_cache["data"] and (now - _top_coins_cache["timestamp"]) < _top_coins_cache["ttl"]:
            cached_data = _top_coins_cache["data"][:limit]
            return {
                "coins": cached_data,
                "count": len(cached_data),
                "updated_at": datetime.fromtimestamp(_top_coins_cache["timestamp"]).isoformat(),
                "cache_hit": True
            }
        
        # 从 CoinGecko 获取数据
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": vs_currency,
            "order": "market_cap_desc",
            "per_page": 250,  # 获取更多以便缓存
            "page": 1,
            "sparkline": False,
            "price_change_percentage": "24h"
        }
        
        resp = http_requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        # 处理数据
        coins = []
        for coin in data:
            coins.append({
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name", ""),
                "market_cap_rank": coin.get("market_cap_rank"),
                "market_cap": coin.get("market_cap"),
                "current_price": coin.get("current_price"),
                "price_change_24h": coin.get("price_change_percentage_24h"),
                "image": coin.get("image"),
                "id": coin.get("id")  # CoinGecko ID, 用于详细查询
            })
        
        # 更新缓存
        _top_coins_cache["data"] = coins
        _top_coins_cache["timestamp"] = now
        
        result_coins = coins[:limit]
        return {
            "coins": result_coins,
            "count": len(result_coins),
            "updated_at": datetime.fromtimestamp(now).isoformat(),
            "cache_hit": False
        }
        
    except http_requests.exceptions.RequestException as e:
        logger.error(f"CoinGecko API request failed: {e}")
        # 如果有缓存数据，返回缓存（即使过期）
        if _top_coins_cache["data"]:
            cached_data = _top_coins_cache["data"][:limit]
            return {
                "coins": cached_data,
                "count": len(cached_data),
                "updated_at": datetime.fromtimestamp(_top_coins_cache["timestamp"]).isoformat(),
                "cache_hit": True,
                "stale": True,
                "error": str(e)
            }
        raise HTTPException(status_code=503, detail=f"CoinGecko API unavailable: {e}")
    except Exception as e:
        logger.error(f"Error fetching top coins: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
