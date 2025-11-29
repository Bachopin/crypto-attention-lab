"""
Crypto Attention Lab - FastAPI Backend
提供价格、注意力和新闻数据的 REST API
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi import Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from src.research.attention_regimes import analyze_attention_regimes
from datetime import datetime
import pandas as pd
import logging
import os
import subprocess

from src.data.db_storage import (
    load_price_data,
    load_attention_data,
    load_news_data,
    get_available_symbols,
    get_db,
)
from src.database.models import Symbol, get_session
from src.events.attention_events import detect_attention_events
from src.backtest.basic_attention_factor import run_backtest_basic_attention
from src.backtest.strategy_templates import AttentionCondition
from src.backtest.attention_rotation import run_attention_rotation_backtest
from src.features.event_performance import compute_event_performance
from src.features.node_influence import load_node_carry_factors

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# ==================== 辅助函数 ====================


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


import asyncio
from contextlib import asynccontextmanager

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


# 注意：Attention Features 更新已整合到 scheduled_price_update 中
# 价格更新后会立即计算 Attention，无需独立的定时任务


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理
    启动时开启后台任务
    
    后台任务说明：
    - news_task: 每小时拉取全局新闻数据到数据库
    - price_task: 每2分钟更新价格，并在更新后立即计算 Attention Features
    """
    # 启动后台任务
    news_task = asyncio.create_task(scheduled_news_update())
    price_task = asyncio.create_task(scheduled_price_update())
    
    logger.info("[Scheduler] Background tasks started: news_update (hourly), price_update (2min)")
    logger.info("[Scheduler] Attention features will be calculated automatically after price updates")
    
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
                # 验证时间范围合理性
                if start_dt.year < 2009:
                    raise ValueError(f"Start time {start_dt} is too early (before 2009)")
                if start_dt > pd.Timestamp.now(tz='UTC'):
                    raise ValueError(f"Start time {start_dt} is in the future")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
                # 验证时间范围合理性
                if end_dt.year < 2009:
                    raise ValueError(f"End time {end_dt} is too early (before 2009)")
                if end_dt > pd.Timestamp.now(tz='UTC') + pd.Timedelta(days=1):
                    raise ValueError(f"End time {end_dt} is too far in the future")
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
                # 验证时间范围合理性
                if start_dt.year < 2009:
                    raise ValueError(f"Start time {start_dt} is too early (before 2009)")
                if start_dt > pd.Timestamp.now(tz='UTC'):
                    raise ValueError(f"Start time {start_dt} is in the future")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
                # 验证时间范围合理性
                if end_dt.year < 2009:
                    raise ValueError(f"End time {end_dt} is too early (before 2009)")
                if end_dt > pd.Timestamp.now(tz='UTC') + pd.Timedelta(days=1):
                    raise ValueError(f"End time {end_dt} is too far in the future")
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
                # 验证时间范围合理性（不早于2009年，比特币诞生）
                if start_dt.year < 2009:
                    raise ValueError(f"Start time {start_dt} is too early (before 2009)")
                if start_dt > pd.Timestamp.now(tz='UTC'):
                    raise ValueError(f"Start time {start_dt} is in the future")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
                # 验证时间范围合理性
                if end_dt.year < 2009:
                    raise ValueError(f"End time {end_dt} is too early (before 2009)")
                if end_dt > pd.Timestamp.now(tz='UTC') + pd.Timedelta(days=1):
                    raise ValueError(f"End time {end_dt} is too far in the future")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        # 若提供 before，则将 end_dt 覆盖为 before 并可选设置默认窗口
        if before:
            try:
                before_dt = pd.to_datetime(before, utc=True)
                # 验证 before 时间
                if before_dt.year < 2009:
                    raise ValueError(f"Before time {before_dt} is too early (before 2009)")
                if before_dt > pd.Timestamp.now(tz='UTC') + pd.Timedelta(days=1):
                    raise ValueError(f"Before time {before_dt} is too far in the future")
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
        attention_condition = _parse_attention_condition(payload.get("attention_condition"))
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
            attention_condition=attention_condition,
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
        attention_condition = _parse_attention_condition(payload.get("attention_condition"))
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
                "attention_source": attention_source,
                "symbols": symbols,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in backtest_basic_attention_multi: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Research: Attention Regimes ====================

@app.post("/api/research/attention-regimes")
def research_attention_regimes(payload: dict = Body(...)):
    """多币种 attention regime 研究分析接口"""
    symbols = payload.get("symbols")
    if not symbols or not isinstance(symbols, list):
        raise HTTPException(status_code=400, detail="symbols must be a non-empty list")

    normalized_symbols = []
    for sym in symbols:
        if sym is None:
            continue
        name = str(sym).strip()
        if name:
            normalized_symbols.append(name.upper())

    if not normalized_symbols:
        raise HTTPException(status_code=400, detail="symbols must contain at least one valid entry")

    raw_lookahead = payload.get("lookahead_days")
    if raw_lookahead is None:
        lookahead_days = [7, 30]
    elif isinstance(raw_lookahead, list):
        lookahead_days = raw_lookahead
    elif isinstance(raw_lookahead, str):
        lookahead_days = [item.strip() for item in raw_lookahead.split(",") if item.strip()]
    else:
        raise HTTPException(status_code=400, detail="lookahead_days must be a list or comma string")

    try:
        lookahead_days = [int(day) for day in lookahead_days]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="lookahead_days must contain integers") from None

    split_quantiles = payload.get("split_quantiles")
    if split_quantiles is not None:
        if not isinstance(split_quantiles, list):
            raise HTTPException(status_code=400, detail="split_quantiles must be a list of floats")
        try:
            split_quantiles = [float(q) for q in split_quantiles]
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="split_quantiles must contain numeric values") from None

    attention_source = payload.get("attention_source", "composite")
    split_method = payload.get("split_method", "tercile")

    start = payload.get("start")
    end = payload.get("end")

    try:
        start_dt = pd.to_datetime(start, utc=True) if start else None
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid start datetime: {exc}") from None

    try:
        end_dt = pd.to_datetime(end, utc=True) if end else None
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid end datetime: {exc}") from None

    try:
        result = analyze_attention_regimes(
            symbols=normalized_symbols,
            lookahead_days=lookahead_days,
            attention_source=attention_source,
            split_method=split_method,
            split_quantiles=split_quantiles,
            start=start_dt,
            end=end_dt,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception as exc:
        logger.error("Error in research_attention_regimes", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


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
    try:
        session = get_session()
        # 显示：auto_update=True 或 曾经更新过价格（last_price_update 不为空）的代币
        # 这样暂停后的代币仍然会显示在列表中
        from sqlalchemy import or_
        symbols = session.query(Symbol).filter(
            or_(
                Symbol.auto_update_price == True,
                Symbol.last_price_update.isnot(None)
            )
        ).all()
        
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
async def enable_auto_update(
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
            "enabled": ["BTC", "ETH", "SOL"],
            "message": "Auto-update enabled and initial data fetch triggered"
        }
    """
    from src.features.attention_features import process_attention_features
    from src.data.realtime_price_updater import get_realtime_updater
    
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
        
        # 触发初始数据更新和 attention 计算
        updater = get_realtime_updater()
        initialized = []
        
        for symbol_name in enabled:
            try:
                logger.info(f"[Initialize] Starting initialization for {symbol_name}...")
                
                # 1. 检查是否有价格数据
                from src.data.db_storage import load_price_data
                price_data = load_price_data(symbol_name, timeframe='1d')
                if isinstance(price_data, tuple):
                    df, _ = price_data
                else:
                    df = price_data
                
                needs_price_fetch = df is None or df.empty
                
                # 如果没有数据或数据过旧（超过7天），拉取历史数据
                if not needs_price_fetch and not df.empty:
                    last_date = pd.to_datetime(df['datetime']).max()
                    days_old = (pd.Timestamp.now(tz='UTC') - last_date).days
                    if days_old > 7:
                        needs_price_fetch = True
                        logger.info(f"[Initialize] {symbol_name} price data is {days_old} days old, will refresh")
                
                # 2. 拉取价格数据（如果需要）
                if needs_price_fetch:
                    logger.info(f"[Initialize] Fetching historical prices for {symbol_name} (≥1 year)...")
                    await updater.update_single_symbol(symbol_name, last_update=None)
                else:
                    logger.info(f"[Initialize] {symbol_name} has recent price data, skipping fetch")
                
                # 3. 计算 Attention Features
                logger.info(f"[Initialize] Calculating attention features for {symbol_name}...")
                await asyncio.to_thread(process_attention_features, symbol_name, freq='D', save_to_db=True)
                
                initialized.append(symbol_name)
                logger.info(f"[Initialize] ✅ {symbol_name} initialization completed")
                
            except Exception as e:
                logger.error(f"[Initialize] ❌ Failed to initialize {symbol_name}: {e}", exc_info=True)
                # 继续处理其他 symbol，不中断整个流程
        
        return {
            "status": "success",
            "enabled": enabled,
            "initialized": initialized,
            "message": f"Enabled and initialized {len(initialized)}/{len(enabled)} symbols"
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
                sym.is_active = False
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


@app.post("/api/attention/trigger-update")
async def trigger_attention_update(
    payload: dict = Body(...)
):
    """
    手动触发指定标的的 Attention Features 更新
    
    Request:
        {
            "symbols": ["BTC", "ETH"],  // 可选，不指定则更新所有启用的代币
            "freq": "D"  // 可选，默认 "D"（日线），可选 "4H"
        }
    
    Response:
        {
            "status": "success",
            "updated": ["BTC", "ETH"],
            "message": "Attention features updated successfully"
        }
    """
    from src.features.attention_features import process_attention_features
    
    try:
        symbols = payload.get("symbols", [])
        freq = payload.get("freq", "D")
        
        # 如果没有指定 symbols，获取所有启用自动更新的代币
        if not symbols:
            session = get_session()
            enabled_symbols = session.query(Symbol).filter(
                Symbol.auto_update_price == True
            ).all()
            symbols = [s.symbol for s in enabled_symbols]
            session.close()
            
            if not symbols:
                return {
                    "status": "warning",
                    "updated": [],
                    "message": "No symbols enabled for auto-update"
                }
        
        updated = []
        errors = []
        
        for symbol_name in symbols:
            symbol_name = symbol_name.upper()
            try:
                logger.info(f"Manually triggering attention update for {symbol_name} (freq={freq})...")
                
                # 在线程池中运行同步函数，避免阻塞
                await asyncio.to_thread(process_attention_features, symbol_name, freq=freq)
                
                updated.append(symbol_name)
                logger.info(f"✅ Attention features updated for {symbol_name}")
                
            except Exception as e:
                error_msg = f"{symbol_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ Failed to update attention for {symbol_name}: {e}")
        
        response = {
            "status": "success" if updated else "error",
            "updated": updated,
            "message": f"Updated {len(updated)} symbol(s)"
        }
        
        if errors:
            response["errors"] = errors
            response["message"] += f", {len(errors)} failed"
        
        return response
        
    except Exception as e:
        logger.error(f"Error triggering attention update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 注意力轮动策略回测 API ====================

@app.post("/api/backtest/attention-rotation")
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


# ==================== State Snapshot API ====================

@app.get("/api/state/snapshot")
def get_state_snapshot(
    symbol: str = Query(..., description="标的符号，如 ZEC, BTC"),
    timeframe: str = Query("1d", description="时间粒度: 1d 或 4h"),
    window_days: int = Query(30, ge=7, le=365, description="特征计算窗口天数"),
):
    """
    获取指定 symbol 当前的状态快照
    
    返回该 symbol 截至当前时刻的多维状态特征向量，包括：
    - 价格/波动维度（累计收益、波动率、成交量）
    - 注意力维度（合成注意力、新闻热度、趋势变化）
    - 情绪维度（sentiment、bullish/bearish 比例）
    - 通道结构（各通道占比）
    
    状态快照可用于：
    - 相似模式检索（Scenario Engine）
    - 情景分析（类似历史模式的价格表现）
    - 多因子综合评估
    
    Request:
        GET /api/state/snapshot?symbol=ZEC&timeframe=1d&window_days=30
    
    Response:
        {
            "symbol": "ZEC",
            "as_of": "2025-11-29T12:00:00+00:00",
            "timeframe": "1d",
            "window_days": 30,
            "features": {
                "ret_window": 0.52,
                "vol_window": -0.31,
                "volume_zscore": 1.24,
                "att_composite_z": 0.87,
                "att_news_z": 0.65,
                "att_trend_7d": 0.12,
                "att_spike_flag": 0,
                "att_news_share": 0.45,
                "att_google_share": 0.35,
                "att_twitter_share": 0.20,
                "sentiment_mean_window": 0.15,
                "bullish_minus_bearish": 0.32
            },
            "raw_stats": {
                "close_price": 45.67,
                "high_window": 52.30,
                "low_window": 38.12,
                "avg_volume_7d": 12345678.0,
                "composite_attention_score": 2.34,
                "news_count_7d": 15,
                ...
            }
        }
    
    Error Response (404):
        {
            "detail": "No data available for symbol ZEC"
        }
    """
    from src.research.state_snapshot import compute_state_snapshot
    
    try:
        # 验证 timeframe
        if timeframe not in ("1d", "4h"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe '{timeframe}'. Must be '1d' or '4h'"
            )
        
        # 计算状态快照
        snapshot = compute_state_snapshot(
            symbol=symbol,
            as_of=None,  # 使用当前时间
            timeframe=timeframe,
            window_days=window_days,
        )
        
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for symbol {symbol}. "
                       f"Please ensure price and attention data exist for this symbol."
            )
        
        # 转换为可序列化的字典
        result = snapshot.to_dict()
        
        logger.info(
            f"State snapshot returned for {symbol}: "
            f"{len(snapshot.features)} features, {len(snapshot.raw_stats)} raw stats"
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_state_snapshot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/state/snapshot/batch")
def get_state_snapshots_batch(
    payload: dict = Body(...)
):
    """
    批量获取多个 symbol 的状态快照
    
    Request:
        POST /api/state/snapshot/batch
        {
            "symbols": ["ZEC", "BTC", "ETH"],
            "timeframe": "1d",
            "window_days": 30
        }
    
    Response:
        {
            "snapshots": {
                "ZEC": { ... snapshot data ... },
                "BTC": { ... snapshot data ... },
                "ETH": null  // 如果无数据
            },
            "meta": {
                "requested": 3,
                "success": 2,
                "failed": 1
            }
        }
    """
    from src.research.state_snapshot import compute_state_snapshots_batch
    
    try:
        symbols = payload.get("symbols", [])
        if not symbols or not isinstance(symbols, list):
            raise HTTPException(status_code=400, detail="symbols must be a non-empty list")
        
        timeframe = payload.get("timeframe", "1d")
        if timeframe not in ("1d", "4h"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe '{timeframe}'. Must be '1d' or '4h'"
            )
        
        window_days = int(payload.get("window_days", 30))
        if window_days < 7 or window_days > 365:
            raise HTTPException(
                status_code=400,
                detail="window_days must be between 7 and 365"
            )
        
        # 批量计算
        snapshots = compute_state_snapshots_batch(
            symbols=symbols,
            as_of=None,
            timeframe=timeframe,
            window_days=window_days,
        )
        
        # 转换结果
        result_snapshots = {}
        success_count = 0
        failed_count = 0
        
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
                "requested": len(symbols),
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

@app.get("/api/state/similar-cases")
def get_similar_cases(
    symbol: str = Query(..., description="目标币种符号，如 ZEC, BTC"),
    timeframe: str = Query("1d", description="时间粒度: 1d 或 4h"),
    window_days: int = Query(30, ge=7, le=365, description="特征计算窗口天数"),
    top_k: int = Query(50, ge=1, le=500, description="返回的相似样本数量"),
    max_history_days: int = Query(365, ge=30, le=1095, description="最大历史回溯天数"),
    include_same_symbol: bool = Query(True, description="是否包含相同币种的历史状态"),
):
    """
    获取当前 symbol 在给定 timeframe/window_days 下的相似历史状态样本列表。
    
    本接口是 Scenario Engine 的核心功能，用于：
    - 查找历史上与当前市场状态相似的时刻
    - 支持跨币种的相似模式检索
    - 为情景分析提供数据支持
    
    算法说明：
    - 基于 StateSnapshot 的多维特征向量计算欧氏距离
    - 自动排除目标时间点附近 ±7 天的样本（避免信息泄露）
    - 返回按距离从小到大排序的 Top-K 相似样本
    
    Request:
        GET /api/state/similar-cases?symbol=ZEC&timeframe=1d&window_days=30&top_k=50
    
    Response:
        {
            "target": {
                "symbol": "ZEC",
                "as_of": "2025-11-29T12:00:00+00:00",
                "features": {...},
                "raw_stats": {...}
            },
            "similar_cases": [
                {
                    "symbol": "ZEC",
                    "datetime": "2024-06-15T00:00:00+00:00",
                    "timeframe": "1d",
                    "distance": 1.234,
                    "similarity": 0.85,
                    "snapshot_summary": {
                        "close_price": 42.50,
                        "return_window_pct": 0.12,
                        ...
                    }
                },
                ...
            ],
            "meta": {
                "total_candidates_processed": 365,
                "results_returned": 50,
                "message": "Found 50 similar historical states"
            }
        }
    
    Error Response (404):
        {
            "detail": "No data available for symbol ZEC"
        }
    """
    from src.research.state_snapshot import compute_state_snapshot
    from src.research.similar_states import find_similar_states
    
    try:
        # 验证 timeframe
        if timeframe not in ("1d", "4h"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe '{timeframe}'. Must be '1d' or '4h'"
            )
        
        # 计算目标状态快照
        target = compute_state_snapshot(
            symbol=symbol,
            as_of=None,  # 使用当前时间
            timeframe=timeframe,
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
            timeframe=timeframe,
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


@app.post("/api/state/similar-cases/custom")
def get_similar_cases_custom(
    payload: dict = Body(...)
):
    """
    自定义参数的相似状态检索（高级用法）
    
    支持指定候选币种列表、距离度量方式等高级参数。
    
    Request:
        POST /api/state/similar-cases/custom
        {
            "symbol": "ZEC",
            "timeframe": "1d",
            "window_days": 30,
            "top_k": 100,
            "max_history_days": 365,
            "candidate_symbols": ["ZEC", "BTC", "ETH"],  // 可选，限定候选范围
            "distance_metric": "euclidean",  // 可选: euclidean 或 cosine
            "include_same_symbol": true,  // 可选
            "exclusion_days": 7  // 可选，排除目标时间附近的天数
        }
    
    Response:
        同 GET /api/state/similar-cases
    """
    from src.research.state_snapshot import compute_state_snapshot
    from src.research.similar_states import find_similar_states
    
    try:
        # 提取参数
        symbol = payload.get("symbol")
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol is required")
        
        timeframe = payload.get("timeframe", "1d")
        if timeframe not in ("1d", "4h"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe '{timeframe}'. Must be '1d' or '4h'"
            )
        
        window_days = int(payload.get("window_days", 30))
        if window_days < 7 or window_days > 365:
            raise HTTPException(
                status_code=400,
                detail="window_days must be between 7 and 365"
            )
        
        top_k = int(payload.get("top_k", 50))
        max_history_days = int(payload.get("max_history_days", 365))
        distance_metric = payload.get("distance_metric", "euclidean")
        include_same_symbol = payload.get("include_same_symbol", True)
        exclusion_days = int(payload.get("exclusion_days", 7))
        
        # 候选币种
        candidate_symbols = payload.get("candidate_symbols")
        if not candidate_symbols:
            candidate_symbols = get_available_symbols()
        
        # 计算目标状态
        target = compute_state_snapshot(
            symbol=symbol,
            as_of=None,
            timeframe=timeframe,
            window_days=window_days,
        )
        
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for symbol {symbol}"
            )
        
        # 查找相似状态
        similar_states = find_similar_states(
            target=target,
            candidate_symbols=candidate_symbols,
            timeframe=timeframe,
            window_days=window_days,
            top_k=top_k,
            max_history_days=max_history_days,
            exclusion_days=exclusion_days,
            distance_metric=distance_metric,
            include_same_symbol=include_same_symbol,
            verbose=False,
        )
        
        # 转换结果
        similar_cases = [state.to_dict() for state in similar_states]
        
        return {
            "target": target.to_dict(),
            "similar_cases": similar_cases,
            "meta": {
                "results_returned": len(similar_cases),
                "distance_metric": distance_metric,
                "candidate_symbols_count": len(candidate_symbols),
                "message": f"Found {len(similar_cases)} similar states using {distance_metric} distance"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_similar_cases_custom: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Scenario Analysis API ====================

@app.get("/api/state/scenarios")
def get_state_scenarios(
    symbol: str = Query(..., description="目标币种符号，如 ZEC, BTC"),
    timeframe: str = Query("1d", description="时间粒度: 1d 或 4h"),
    window_days: int = Query(30, ge=7, le=365, description="特征计算窗口天数"),
    top_k: int = Query(100, ge=10, le=500, description="用于分析的相似样本数量"),
    max_history_days: int = Query(365, ge=30, le=1095, description="最大历史回溯天数"),
    include_sample_details: bool = Query(False, description="是否包含样本详情"),
):
    """
    对当前 symbol 的状态进行基于 Attention 的未来情景分析。
    
    Scenario Engine 核心接口，完成以下流程：
    1. 计算当前 symbol 的状态快照
    2. 查找历史上相似的状态样本
    3. 分析这些样本的后续价格表现
    4. 将样本分类到不同情景（trend_up, spike_and_revert, sideways 等）
    5. 统计各情景的概率、平均收益和风险指标
    
    情景分类说明：
    - trend_up: 持续上涨，价格在观察期内持续走高，回撤可控
    - trend_down: 持续下跌，价格在观察期内持续走低
    - spike_and_revert: 冲高回落，短期内快速上涨后回吐大部分涨幅
    - crash: 急剧下跌，出现大幅回撤
    - sideways: 横盘震荡，价格波动有限，方向不明确
    
    ⚠️ 声明：当前实现为 rule-based/统计版，用于研究和趋势推演，不构成交易建议。
    过往表现不代表未来收益。
    
    Request:
        GET /api/state/scenarios?symbol=ZEC&timeframe=1d&top_k=100
    
    Response:
        {
            "target": {
                "symbol": "ZEC",
                "as_of": "2025-11-29T12:00:00+00:00",
                "features": {...},
                "raw_stats": {...}
            },
            "scenarios": [
                {
                    "label": "sideways",
                    "description": "横盘震荡：价格波动有限，方向不明确，适合区间操作或观望",
                    "sample_count": 45,
                    "probability": 0.45,
                    "avg_return_3d": 0.005,
                    "avg_return_7d": 0.012,
                    "avg_return_30d": 0.025,
                    "max_drawdown_7d": -0.03,
                    "max_drawdown_30d": -0.08,
                    "avg_path": [0, 0.01, 0.02, ...]
                },
                {
                    "label": "trend_up",
                    "description": "持续上涨：价格在观察期内持续走高...",
                    ...
                },
                ...
            ],
            "meta": {
                "total_similar_samples": 100,
                "valid_samples_analyzed": 85,
                "lookahead_days": [3, 7, 30],
                "message": "Scenario analysis complete"
            }
        }
    
    Error Response (404):
        {
            "detail": "No data available for symbol ZEC"
        }
    """
    from src.research.state_snapshot import compute_state_snapshot
    from src.research.similar_states import find_similar_states
    from src.research.scenarios import analyze_scenarios
    
    try:
        # 验证 timeframe
        if timeframe not in ("1d", "4h"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe '{timeframe}'. Must be '1d' or '4h'"
            )
        
        # Step 1: 计算目标状态快照
        target = compute_state_snapshot(
            symbol=symbol,
            as_of=None,
            timeframe=timeframe,
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
        
        similar_states = find_similar_states(
            target=target,
            candidate_symbols=candidate_symbols,
            timeframe=timeframe,
            window_days=window_days,
            top_k=top_k,
            max_history_days=max_history_days,
            include_same_symbol=True,
            verbose=False,
        )
        
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


@app.post("/api/state/scenarios/custom")
def get_state_scenarios_custom(
    payload: dict = Body(...)
):
    """
    自定义参数的情景分析（高级用法）
    
    支持自定义 lookahead 窗口、分类阈值等高级参数。
    
    Request:
        POST /api/state/scenarios/custom
        {
            "symbol": "ZEC",
            "timeframe": "1d",
            "window_days": 30,
            "top_k": 100,
            "max_history_days": 365,
            "lookahead_days": [3, 7, 14, 30],  // 自定义 lookahead 窗口
            "candidate_symbols": ["ZEC", "BTC", "ETH"],  // 可选
            "include_sample_details": false  // 是否包含样本详情
        }
    
    Response:
        同 GET /api/state/scenarios
    """
    from src.research.state_snapshot import compute_state_snapshot
    from src.research.similar_states import find_similar_states
    from src.research.scenarios import analyze_scenarios
    
    try:
        # 提取参数
        symbol = payload.get("symbol")
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol is required")
        
        timeframe = payload.get("timeframe", "1d")
        if timeframe not in ("1d", "4h"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe '{timeframe}'. Must be '1d' or '4h'"
            )
        
        window_days = int(payload.get("window_days", 30))
        top_k = int(payload.get("top_k", 100))
        max_history_days = int(payload.get("max_history_days", 365))
        include_sample_details = payload.get("include_sample_details", False)
        
        # 自定义 lookahead 窗口
        lookahead_days = payload.get("lookahead_days", [3, 7, 30])
        if not isinstance(lookahead_days, list):
            raise HTTPException(
                status_code=400,
                detail="lookahead_days must be a list of integers"
            )
        lookahead_days = [int(d) for d in lookahead_days]
        
        # 候选币种
        candidate_symbols = payload.get("candidate_symbols")
        if not candidate_symbols:
            candidate_symbols = get_available_symbols()
        
        # Step 1: 计算目标状态
        target = compute_state_snapshot(
            symbol=symbol,
            as_of=None,
            timeframe=timeframe,
            window_days=window_days,
        )
        
        if target is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for symbol {symbol}"
            )
        
        # Step 2: 查找相似状态
        similar_states = find_similar_states(
            target=target,
            candidate_symbols=candidate_symbols,
            timeframe=timeframe,
            window_days=window_days,
            top_k=top_k,
            max_history_days=max_history_days,
            include_same_symbol=True,
            verbose=False,
        )
        
        if not similar_states:
            return {
                "target": target.to_dict(),
                "scenarios": [],
                "meta": {
                    "total_similar_samples": 0,
                    "valid_samples_analyzed": 0,
                    "lookahead_days": lookahead_days,
                    "message": "No similar historical states found"
                }
            }
        
        # Step 3: 分析情景
        scenarios = analyze_scenarios(
            target=target,
            similar_states=similar_states,
            lookahead_days=lookahead_days,
            include_sample_details=include_sample_details,
        )
        
        valid_samples = sum(s.sample_count for s in scenarios)
        scenarios_data = [s.to_dict() for s in scenarios]
        
        return {
            "target": target.to_dict(),
            "scenarios": scenarios_data,
            "meta": {
                "total_similar_samples": len(similar_states),
                "valid_samples_analyzed": valid_samples,
                "lookahead_days": lookahead_days,
                "candidate_symbols_count": len(candidate_symbols),
                "message": f"Custom scenario analysis complete: {len(scenarios)} scenarios identified"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_state_scenarios_custom: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
