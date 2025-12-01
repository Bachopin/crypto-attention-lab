"""
Crypto Attention Lab - FastAPI Backend
提供价格、注意力和新闻数据的 REST API
支持 WebSocket 实时数据流
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import market_data, attention, backtest, research, system
from src.api.websocket_routes import (
    websocket_price_endpoint,
    websocket_attention_endpoint,
    get_ws_manager,
)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 后台任务调度 ====================

async def scheduled_news_update():
    """后台任务：定期聚合新闻数据（多源）
    频率：NEWS_UPDATE_INTERVAL（默认 1 小时）
    使用 settings 中的可配置间隔，统一管理调度参数。
    """
    from scripts.fetch_news_data import run_news_fetch_pipeline
    from src.config.settings import NEWS_UPDATE_INTERVAL

    startup_delay = 30  # 避免与价格任务启动拥堵
    logger.info(f"[Scheduler] News update will start in {startup_delay}s (interval={NEWS_UPDATE_INTERVAL}s)...")
    await asyncio.sleep(startup_delay)

    while True:
        try:
            logger.info("[Scheduler] Starting news aggregation cycle...")
            await asyncio.to_thread(run_news_fetch_pipeline, days=1)
            logger.info(f"[Scheduler] News aggregation completed. Sleeping {NEWS_UPDATE_INTERVAL}s.")
        except asyncio.CancelledError:
            logger.info("[Scheduler] News update task cancelled")
            break
        except Exception as e:
            logger.error(f"[Scheduler] News update failed: {e}", exc_info=True)
        finally:
            # 确保即使异常也能继续调度
            await asyncio.sleep(NEWS_UPDATE_INTERVAL)


async def scheduled_price_update():
    """后台任务：实时价格与级联注意力更新
    频率：PRICE_UPDATE_INTERVAL（默认 10 分钟），统一使用 settings 配置。
    """
    from src.data.realtime_price_updater import get_realtime_updater
    from src.config.settings import PRICE_UPDATE_INTERVAL

    startup_delay = 10
    logger.info(f"[Scheduler] Price update will start in {startup_delay}s (interval={PRICE_UPDATE_INTERVAL}s)...")
    await asyncio.sleep(startup_delay)

    try:
        # 使用配置间隔（不再硬编码 300 秒）
        updater = get_realtime_updater(update_interval=PRICE_UPDATE_INTERVAL)
        await updater.run()
    except asyncio.CancelledError:
        logger.info("[Scheduler] Price update task cancelled")
    except Exception as e:
        logger.error(f"[Scheduler] Price update fatal error: {e}", exc_info=True)


async def warmup_binance_websocket():
    """
    预热 Binance WebSocket 连接
    在服务启动时预先连接，减少客户端首次订阅的延迟
    """
    await asyncio.sleep(2)  # 等待服务器完全就绪
    
    try:
        ws_manager = get_ws_manager()
        # 预订阅主流币种
        major_symbols = ['BTC', 'ETH', 'BNB', 'SOL']
        for symbol in major_symbols:
            await ws_manager._ensure_binance_subscription(symbol)
        logger.info(f"[WebSocket] Pre-warmed Binance subscriptions for {major_symbols}")
    except Exception as e:
        logger.warning(f"[WebSocket] Failed to pre-warm Binance WebSocket: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理
    启动时开启后台任务
    """
    # 启动后台任务
    news_task = asyncio.create_task(scheduled_news_update())
    price_task = asyncio.create_task(scheduled_price_update())
    warmup_task = asyncio.create_task(warmup_binance_websocket())
    
    from src.config.settings import PRICE_UPDATE_INTERVAL, NEWS_UPDATE_INTERVAL
    logger.info("[Scheduler] Background tasks started (delayed startup)")
    logger.info(f"[Scheduler] Price interval={PRICE_UPDATE_INTERVAL}s, News interval={NEWS_UPDATE_INTERVAL}s")
    logger.info("[Scheduler] Attention features cascade after each price batch (1h cooldown)")
    logger.info("[WebSocket] Real-time WebSocket endpoints available at /ws/price and /ws/attention")
    logger.info("[WebSocket] Binance WebSocket will pre-warm in 2s")
    
    yield
    
    # 关闭时取消任务
    logger.info("[Shutdown] Cancelling background tasks...")
    tasks = [news_task, price_task, warmup_task]
    for task in tasks:
        task.cancel()
    
    # 等待所有任务完成清理
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("[Shutdown] Background tasks stopped")
    
    # 停止 WebSocket 管理器
    try:
        ws_manager = get_ws_manager()
        if ws_manager.binance_ws and hasattr(ws_manager.binance_ws, 'stop'):
            await ws_manager.binance_ws.stop()
            logger.info("[WebSocket] Binance WebSocket stopped")
    except Exception as e:
        logger.warning(f"[WebSocket] Error stopping Binance WebSocket: {e}")
    
    # 清理数据库连接池
    try:
        from src.database.models import engine
        if engine:
            engine.dispose()
            logger.info("[Shutdown] Database connections closed")
    except Exception as e:
        logger.warning(f"[Shutdown] Error closing database: {e}")
        logger.info("[Scheduler] News task cancelled")
    try:
        await price_task
    except asyncio.CancelledError:
        logger.info("[Scheduler] Price task cancelled")


# 创建 FastAPI 应用
app = FastAPI(
    title="Crypto Attention Lab API",
    description="API for cryptocurrency attention analysis and price data. Supports WebSocket for real-time updates.",
    version="1.0.0",
    lifespan=lifespan
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境全开放，生产环境需要收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 注册路由 ====================

app.include_router(market_data.router)
app.include_router(attention.router)
app.include_router(backtest.router)
app.include_router(research.router)
app.include_router(system.router)

# ==================== WebSocket 端点 ====================

@app.websocket("/ws/price")
async def ws_price(websocket: WebSocket):
    """
    实时价格数据 WebSocket 端点
    """
    await websocket_price_endpoint(websocket)


@app.websocket("/ws/attention")
async def ws_attention(websocket: WebSocket):
    """
    实时注意力数据 WebSocket 端点
    """
    await websocket_attention_endpoint(websocket)


@app.get("/api/ws/stats", tags=["System"])
def get_websocket_stats():
    """获取 WebSocket 连接统计信息"""
    ws_manager = get_ws_manager()
    stats = ws_manager.get_stats()
    
    # 添加更详细的 Binance WS 状态
    if ws_manager.binance_ws:
        stats["binance_details"] = {
            "is_running": ws_manager.binance_ws.is_running,
            "websocket_connected": ws_manager.binance_ws.websocket is not None,
            "subscriptions": list(ws_manager.binance_ws.subscriptions),
            "callbacks_registered": list(ws_manager.binance_ws.callbacks.keys()),
            "tasks_count": len(ws_manager.binance_ws._tasks),
        }
    else:
        stats["binance_details"] = None
    
    return stats


# ==================== 健康检查与根路径 ====================

@app.get("/health", tags=["System"])
@app.get("/ping", tags=["System"])
def health_check():
    """健康检查端点"""
    ws_manager = get_ws_manager()
    return {
        "status": "healthy",
        "service": "Crypto Attention Lab API",
        "version": "1.0.0",
        "websocket": {
            "clients": ws_manager.get_stats()["total_clients"],
            "binance_connected": ws_manager.get_stats()["binance_connected"]
        }
    }

@app.get("/", tags=["System"])
def root():
    """API 根路径"""
    return {
        "message": "Crypto Attention Lab API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health or /ping",
            "symbols": "/api/symbols",
            "price": "/api/price?symbol=ZECUSDT&timeframe=1d",
            "attention": "/api/attention?symbol=ZEC",
            "news": "/api/news?symbol=ZEC",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
