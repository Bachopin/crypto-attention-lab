 
"""
Crypto Attention Lab - FastAPI Backend
提供价格、注意力和新闻数据的 REST API
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi import Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
import pandas as pd
import logging
import os
import subprocess

from src.data.db_storage import (
    load_price_data,
    load_attention_data,
    load_news_data,
    get_available_symbols
)
from src.events.attention_events import detect_attention_events
from src.backtest.basic_attention_factor import run_backtest_basic_attention
from src.features.event_performance import compute_event_performance
from src.features.node_influence import load_node_carry_factors

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import asyncio
from contextlib import asynccontextmanager

# ...existing code...

# ==================== 后台任务调度 ====================

async def scheduled_news_update():
    """
    后台任务：定期更新新闻数据
    每小时运行一次
    """
    from scripts.fetch_news_data import run_news_fetch_pipeline
    
    while True:
        try:
            logger.info("[Scheduler] Starting hourly news update...")
            # 在线程池中运行同步函数，避免阻塞事件循环
            await asyncio.to_thread(run_news_fetch_pipeline, days=1)
            logger.info("[Scheduler] News update completed. Sleeping for 1 hour.")
        except Exception as e:
            logger.error(f"[Scheduler] News update failed: {e}")
        
        # 等待 1 小时
        await asyncio.sleep(3600)


async def scheduled_price_update():
    """
    后台任务：实时价格更新
    每 2 分钟运行一次
    """
    from src.data.realtime_price_updater import get_realtime_updater
    
    updater = get_realtime_updater(update_interval=120)
    await updater.run()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理
    启动时开启后台任务
    """
    # 启动后台任务
    news_task = asyncio.create_task(scheduled_news_update())
    price_task = asyncio.create_task(scheduled_price_update())
    
    yield
    
    # 关闭时取消任务
    news_task.cancel()
    price_task.cancel()
    try:
        await news_task
    except asyncio.CancelledError:
        logger.info("[Scheduler] News task cancelled")
    try:
        await price_task
    except asyncio.CancelledError:
        logger.info("[Scheduler] Price task cancelled")

# 创建 FastAPI 应用
app = FastAPI(
    title="Crypto Attention Lab API",
    description="API for cryptocurrency attention analysis and price data",
    version="0.1.0",
    lifespan=lifespan
)

# ...existing code...
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境全开放，生产环境需要收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 健康检查 ====================

@app.get("/health")
@app.get("/ping")
def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "Crypto Attention Lab API",
        "version": "0.1.0"
    }


# ==================== 价格数据 API ====================

@app.get("/api/price")
def get_price_data(
    symbol: str = Query(default="ZECUSDT", description="交易对符号，如 ZECUSDT"),
    timeframe: str = Query(default="1d", description="时间周期: 1d, 4h, 1h, 15m"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式")
):
    """
    获取价格 OHLCV 数据
    
    返回格式:
    [
        {
            "timestamp": 1700000000000,
            "datetime": "2025-11-26T00:00:00Z",
            "open": 500.0,
            "high": 520.0,
            "low": 495.0,
            "close": 510.0,
            "volume": 12345.67
        }
    ]
    """
    try:
        # 验证 timeframe
        valid_timeframes = ["1d", "4h", "1h", "15m"]
        if timeframe not in valid_timeframes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}"
            )
        
        # 解析时间参数
        start_dt = None
        end_dt = None
        
        if start:
            try:
                start_dt = pd.to_datetime(start, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        # 加载数据（直接从数据库）
        df, is_fallback = load_price_data(symbol, timeframe, start_dt, end_dt)
        
        if df.empty:
            return []
        
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
        
        logger.info(f"Returned {len(result)} price records for {symbol} {timeframe}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_price_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 注意力数据 API ====================

@app.get("/api/attention")
def get_attention_data(
    symbol: str = Query(default="ZEC", description="标的符号，如 ZEC"),
    granularity: str = Query(default="1d", description="时间粒度，目前仅支持 1d"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式")
):
    """
    获取注意力时间序列数据
    
    返回格式:
    [
        {
            "timestamp": 1700000000000,
            "datetime": "2025-11-26T00:00:00Z",
            "attention_score": 80.0,
            "news_count": 4
        }
    ]
    """
    try:
        # 解析时间参数
        start_dt = None
        end_dt = None
        
        if start:
            try:
                start_dt = pd.to_datetime(start, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        # 确保数据存在
        # 数据库模式：直接加载，不预检查
        
        # 加载数据
        df = load_attention_data(symbol, start_dt, end_dt)
        
        if df.empty:
            return []
        
        # 转换为 API 响应格式
        result = []
        for _, row in df.iterrows():
            dt = pd.to_datetime(row['datetime'])
            
            result.append({
                "timestamp": int(dt.timestamp() * 1000),
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


# ==================== 新闻数据 API ====================

@app.get("/api/news")
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
    
    返回格式:
    [
        {
            "datetime": "2025-11-26T23:38:17Z",
            "source": "CoinDesk",
            "title": "ZEC News Sample 8884",
            "url": "https://example.com/news/xxx"
        }
    ]
    """
    try:
        # 解析时间参数
        start_dt = None
        end_dt = None
        
        if start:
            try:
                start_dt = pd.to_datetime(start, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        # 若提供 before，则将 end_dt 覆盖为 before 并可选设置默认窗口
        if before:
            try:
                before_dt = pd.to_datetime(before, utc=True)
                end_dt = before_dt if before_dt else end_dt
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid before time format: {e}")

        # 加载新闻数据
        df = load_news_data(symbol, start_dt, end_dt, limit)

        # 按来源过滤（可选）
        if source and not df.empty and 'source' in df.columns:
            df = df[df['source'] == source]

        # 按时间倒序（最新在前）
        if not df.empty and 'datetime' in df.columns:
            df = df.sort_values(by='datetime', ascending=False)

        # 应用 limit（若提供）
        # 注意：如果使用了 source 过滤，可能需要再次 limit，因为 DB 层的 limit 是在 source 过滤之前
        # 但由于我们现在是在 DB 层 limit，如果 source 过滤导致数据变少，那是符合预期的（返回的是前 N 条中符合 source 的）
        # 如果用户想要 "符合 source 的前 N 条"，则需要在 DB 层支持 source 过滤。
        # 目前 DB 层不支持 source 过滤，所以这里的 limit 只是为了减少内存占用。
        # 为了准确性，如果指定了 source，我们可能需要多取一些数据，或者在 DB 层加 source 过滤。
        # 考虑到复杂性，暂时保持现状，但在 DB 层 limit 可以防止 OOM。
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
            })
        
        logger.info(f"Returned {len(result)} news items for {symbol}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_news_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 新闻总数 API ====================

@app.get("/api/news/count")
def get_news_count(
    symbol: str = Query(default="ALL", description="标的符号，如 ZEC，或 ALL 获取所有"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式"),
    before: Optional[str] = Query(default=None, description="返回该时间之前的新闻（ISO8601），用于游标分页"),
    source: Optional[str] = Query(default=None, description="按新闻源过滤")
):
    """
    获取新闻条目总数（用于分页展示）。
    """
    try:
        start_dt = pd.to_datetime(start, utc=True) if start else None
        end_dt = pd.to_datetime(end, utc=True) if end else None
        if before:
            try:
                before_dt = pd.to_datetime(before, utc=True)
                end_dt = before_dt if before_dt else end_dt
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid before time format: {e}")

        df = load_news_data(symbol, start_dt, end_dt)
        if source and not df.empty and 'source' in df.columns:
            df = df[df['source'] == source]

        return {"total": int(len(df))}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_news_count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 根路径 ====================

@app.get("/")
def root():
    """API 根路径"""
    return {
        "message": "Crypto Attention Lab API",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health or /ping",
            "symbols": "/api/symbols",
            "price": "/api/price?symbol=ZECUSDT&timeframe=1d",
            "attention": "/api/attention?symbol=ZEC",
            "news": "/api/news?symbol=ZEC",
            "update_data": "/api/update-data (POST)"
        },
        "docs": "/docs"
    }


# ==================== 币种列表 API ====================

@app.get("/api/symbols")
def get_symbols():
    """
    获取所有可用币种列表
    
    返回格式:
    {
        "symbols": ["ZEC", "BTC", "ETH", ...],
        "count": 8
    }
    """
    try:
        symbols = get_available_symbols()
        return {
            "symbols": symbols,
            "count": len(symbols)
        }
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 数据更新 ====================

@app.post("/api/update-data")
def update_data(
    update_price: bool = Query(True, description="更新价格数据"),
    update_attention: bool = Query(True, description="更新注意力数据"),
    update_news: bool = Query(True, description="更新新闻数据")
):
    """
    手动触发数据更新

    - update_price: 是否更新价格数据
    - update_attention: 是否更新注意力数据
    - update_news: 是否更新新闻数据
    """
    from pathlib import Path

    results = {
        "status": "success",
        "updated": []
    }

    project_root = Path(__file__).parent.parent.parent
    python_exe = "/Users/mextrel/VSCode/.venv/bin/python"

    try:
        if update_price:
            logger.info("Updating price data...")
            script_path = project_root / "scripts" / "fetch_price_data.py"
            try:
                result = subprocess.run(
                    [python_exe, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(project_root),
                    env={**os.environ, "PYTHONPATH": str(project_root)}
                )

                if result.returncode == 0:
                    results["updated"].append("price")
                    logger.info("Price data updated successfully")
                else:
                    logger.error(f"Failed to update price data: {result.stderr}")
                    results["status"] = "partial"
                    results["error_price"] = result.stderr
            except subprocess.TimeoutExpired:
                logger.error("Price data update timeout (120s)")
                results["status"] = "partial"
                results["error_price"] = "Timeout after 120 seconds"
            except Exception as e:
                logger.error(f"Price data update crashed: {e}")
                results["status"] = "partial"
                results["error_price"] = str(e)

        if update_attention:
            logger.info("Updating attention data...")
            script_path = project_root / "scripts" / "generate_attention_data.py"
            try:
                result = subprocess.run(
                    [python_exe, str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(project_root),
                    env={**os.environ, "PYTHONPATH": str(project_root)}
                )

                if result.returncode == 0:
                    results["updated"].append("attention")
                    logger.info("Attention data updated successfully")
                else:
                    logger.error(f"Failed to update attention data: {result.stderr}")
                    results["status"] = "partial"
                    results["error_attention"] = result.stderr
            except subprocess.TimeoutExpired:
                logger.error("Attention data update timeout (60s)")
                results["status"] = "partial"
                results["error_attention"] = "Timeout after 60 seconds"
            except Exception as e:
                logger.error(f"Attention data update crashed: {e}")
                results["status"] = "partial"
                results["error_attention"] = str(e)

        # Update news data
        if update_news:
            logger.info("Updating news data...")
            script_path = project_root / "scripts" / "fetch_news_data.py"
            try:
                # Manual update: fetch last 30 days to ensure coverage without being too slow
                result = subprocess.run(
                    [python_exe, str(script_path), "--days", "30"],
                    capture_output=True,
                    text=True,
                    timeout=300,  # Increased timeout to 5 minutes
                    cwd=str(project_root),
                    env={**os.environ, "PYTHONPATH": str(project_root)}
                )

                if result.returncode == 0:
                    results["updated"].append("news")
                    logger.info("News data updated successfully")
                    
                    # Regenerate attention features after news update
                    logger.info("Regenerating attention features...")
                    attention_script = project_root / "scripts" / "generate_attention_data.py"
                    try:
                        subprocess.run(
                            [python_exe, str(attention_script)],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            cwd=str(project_root),
                            env={**os.environ, "PYTHONPATH": str(project_root)}
                        )
                        if "attention" not in results["updated"]:
                            results["updated"].append("attention")
                    except Exception as e:
                        logger.warning(f"Attention regeneration failed (non-critical): {e}")
                
                else:
                    logger.error(f"Failed to update news data: {result.stderr}")
            except subprocess.TimeoutExpired:
                logger.error("News data update timeout (300s)")
                results["status"] = "partial"
                results["error_news"] = "Timeout after 300 seconds"
            except Exception as e:
                logger.error(f"News data update crashed: {e}")
                results["status"] = "partial"
                results["error_news"] = result.stderr

        return results

    except Exception as e:
        logger.error(f"Error updating data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ==================== 注意力事件 API ====================

@app.get("/api/attention-events")
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
        events = detect_attention_events(symbol=symbol, start=start_dt, end=end_dt, lookback_days=lookback_days, min_quantile=min_quantile)
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


@app.get("/api/attention-events/performance")
def get_attention_event_performance(
    symbol: str = Query(default="ZEC"),
    lookahead_days: str = Query(default="1,3,5,10"),
):
    """按事件类型与前瞻窗口统计平均收益和样本数。

    lookahead_days: 逗号分隔的天数列表，例如 "1,3,5,10"。
    """
    try:
        days = [int(x) for x in lookahead_days.split(",") if x.strip()]
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


# ==================== 节点带货能力 API ====================

@app.get("/api/node-influence")
def get_node_influence(
    symbol: Optional[str] = Query(None, description="标的符号，如 ZEC，留空返回所有"),
    min_events: int = Query(10, ge=1, description="最小事件样本数过滤"),
    sort_by: str = Query("ir", description="排序字段: ir | mean_excess_return | hit_rate"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数量上限"),
):
    """查询节点带货能力因子。

    返回按节点聚合的统计：
    - symbol, node_id, n_events, mean_excess_return, hit_rate, ir, lookahead, lookback_days
    """

    try:
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


# ==================== 基础回测 API ====================

@app.post("/api/backtest/basic-attention")
def backtest_basic_attention(
    payload: dict = Body(...)
):
    """单币种基础注意力策略回测"""
    try:
        symbol = payload.get("symbol", "ZECUSDT")
        lookback_days = int(payload.get("lookback_days", 30))
        attention_quantile = float(payload.get("attention_quantile", 0.8))
        max_daily_return = float(payload.get("max_daily_return", 0.05))
        holding_days = int(payload.get("holding_days", 3))
        stop_loss_pct = float(payload["stop_loss_pct"]) if "stop_loss_pct" in payload and payload["stop_loss_pct"] is not None else None
        take_profit_pct = float(payload["take_profit_pct"]) if "take_profit_pct" in payload and payload["take_profit_pct"] is not None else None
        max_holding_days = int(payload["max_holding_days"]) if "max_holding_days" in payload and payload["max_holding_days"] is not None else None
        position_size = float(payload.get("position_size", 1.0))
        start = pd.to_datetime(payload.get("start"), utc=True) if payload.get("start") else None
        end = pd.to_datetime(payload.get("end"), utc=True) if payload.get("end") else None
        attention_source = (payload.get("attention_source") or "legacy").lower()
        if attention_source not in {"legacy", "composite"}:
            attention_source = "legacy"
        res = run_backtest_basic_attention(
            symbol=symbol,
            lookback_days=lookback_days,
            attention_quantile=attention_quantile,
            max_daily_return=max_daily_return,
            holding_days=holding_days,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            max_holding_days=max_holding_days,
            position_size=position_size,
            start=start,
            end=end,
            attention_source=attention_source,
        )
        return res
    except Exception as e:
        logger.error(f"Error in backtest_basic_attention: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backtest/basic-attention/multi")
def backtest_basic_attention_multi(
    payload: dict = Body(...)
):
    """多币种基础注意力策略回测

    Request:
        {
            "symbols": ["ZECUSDT", "BTCUSDT"],
            ... 其余参数与单币种回测一致 ...
        }
    """
    try:
        symbols = payload.get("symbols") or []
        if not symbols or not isinstance(symbols, list):
            raise HTTPException(status_code=400, detail="symbols must be a non-empty list")

        lookback_days = int(payload.get("lookback_days", 30))
        attention_quantile = float(payload.get("attention_quantile", 0.8))
        max_daily_return = float(payload.get("max_daily_return", 0.05))
        holding_days = int(payload.get("holding_days", 3))
        stop_loss_pct = float(payload["stop_loss_pct"]) if "stop_loss_pct" in payload and payload["stop_loss_pct"] is not None else None
        take_profit_pct = float(payload["take_profit_pct"]) if "take_profit_pct" in payload and payload["take_profit_pct"] is not None else None
        max_holding_days = int(payload["max_holding_days"]) if "max_holding_days" in payload and payload["max_holding_days"] is not None else None
        position_size = float(payload.get("position_size", 1.0))
        start = pd.to_datetime(payload.get("start"), utc=True) if payload.get("start") else None
        end = pd.to_datetime(payload.get("end"), utc=True) if payload.get("end") else None
        attention_source = (payload.get("attention_source") or "legacy").lower()
        if attention_source not in {"legacy", "composite"}:
            attention_source = "legacy"

        per_symbol_summary = {}
        per_symbol_equity_curves = {}
        per_symbol_meta = {}

        for sym in symbols:
            res = run_backtest_basic_attention(
                symbol=sym,
                lookback_days=lookback_days,
                attention_quantile=attention_quantile,
                max_daily_return=max_daily_return,
                holding_days=holding_days,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                max_holding_days=max_holding_days,
                position_size=position_size,
                start=start,
                end=end,
                attention_source=attention_source,
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
                "attention_source": attention_source,
                "symbols": symbols,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backtest_basic_attention_multi: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 自动更新管理 API ====================

@app.get("/api/auto-update/status")
def get_auto_update_status():
    """
    获取所有标的的自动更新状态
    
    Returns:
        {
            "symbols": [
                {
                    "symbol": "BTC",
                    "auto_update": true,
                    "last_update": "2025-11-27T10:00:00Z",
                    "is_active": true
                },
                ...
            ]
        }
    """
    from src.database.models import Symbol, get_session, get_engine
    
    try:
        session = get_session()
        symbols = session.query(Symbol).all()
        
        result = [{
            "symbol": s.symbol,
            "auto_update": s.auto_update_price,
            "last_update": s.last_price_update.isoformat() if s.last_price_update else None,
            "is_active": s.is_active
        } for s in symbols]
        
        session.close()
        return {"symbols": result}
        
    except Exception as e:
        logger.error(f"Error getting auto-update status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auto-update/enable")
def enable_auto_update(
    payload: dict = Body(...)
):
    """
    启用标的的自动更新
    
    Request:
        {
            "symbols": ["BTC", "ETH", "SOL"]
        }
    
    Response:
        {
            "status": "success",
            "enabled": ["BTC", "ETH", "SOL"]
        }
    """
    from src.database.models import Symbol, get_session, get_engine
    from src.data.db_storage import get_db
    
    try:
        symbols = payload.get("symbols", [])
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        db = get_db()
        session = get_session()
        enabled = []
        
        for symbol_name in symbols:
            symbol_name = symbol_name.upper()
            
            # 获取或创建 Symbol 记录
            sym = db.get_or_create_symbol(session, symbol_name)
            
            # 启用自动更新
            sym.auto_update_price = True
            sym.is_active = True
            enabled.append(symbol_name)
        
        session.commit()
        session.close()
        
        logger.info(f"Enabled auto-update for: {enabled}")
        return {
            "status": "success",
            "enabled": enabled
        }
        
    except Exception as e:
        logger.error(f"Error enabling auto-update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auto-update/disable")
def disable_auto_update(
    payload: dict = Body(...)
):
    """
    禁用标的的自动更新
    
    Request:
        {
            "symbols": ["BTC"]
        }
    """
    from src.database.models import Symbol, get_session
    
    try:
        symbols = payload.get("symbols", [])
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        session = get_session()
        disabled = []
        
        for symbol_name in symbols:
            symbol_name = symbol_name.upper()
            sym = session.query(Symbol).filter_by(symbol=symbol_name).first()
            
            if sym:
                sym.auto_update_price = False
                disabled.append(symbol_name)
        
        session.commit()
        session.close()
        
        logger.info(f"Disabled auto-update for: {disabled}")
        return {
            "status": "success",
            "disabled": disabled
        }
        
    except Exception as e:
        logger.error(f"Error disabling auto-update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auto-update/trigger")
async def trigger_manual_update(
    payload: dict = Body(...)
):
    """
    手动触发指定标的的价格更新
    
    Request:
        {
            "symbols": ["BTC", "ETH"]
        }
    """
    from src.data.realtime_price_updater import get_realtime_updater
    from src.database.models import Symbol, get_session
    
    try:
        symbols = payload.get("symbols", [])
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        updater = get_realtime_updater()
        session = get_session()
        
        updated = []
        for symbol_name in symbols:
            symbol_name = symbol_name.upper()
            sym = session.query(Symbol).filter_by(symbol=symbol_name).first()
            
            last_update = sym.last_price_update if sym else None
            
            # 执行更新
            await updater.update_single_symbol(symbol_name, last_update)
            updated.append(symbol_name)
        
        session.close()
        
        return {
            "status": "success",
            "updated": updated
        }
        
    except Exception as e:
        logger.error(f"Error triggering manual update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
        lookback_days = int(payload.get("lookback_days", 30))
        attention_quantile = float(payload.get("attention_quantile", 0.8))
        max_daily_return = float(payload.get("max_daily_return", 0.05))
        holding_days = int(payload.get("holding_days", 3))
        start = pd.to_datetime(payload.get("start"), utc=True) if payload.get("start") else None
        end = pd.to_datetime(payload.get("end"), utc=True) if payload.get("end") else None
        res = run_backtest_basic_attention(
            symbol=symbol,
            lookback_days=lookback_days,
            attention_quantile=attention_quantile,
            max_daily_return=max_daily_return,
            holding_days=holding_days,
            start=start,
            end=end,
        )
        return res
    except Exception as e:
        logger.error(f"Error in backtest_basic_attention: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
