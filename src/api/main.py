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
    """
    后台任务：定期更新新闻数据
    每 30 分钟运行一次
    """
    from scripts.fetch_news_data import run_news_fetch_pipeline
    
    # 启动延迟：等待服务器就绪后再开始
    logger.info("[Scheduler] News update will start in 30 seconds...")
    await asyncio.sleep(30)
    
    while True:
        try:
            logger.info("[Scheduler] Starting news update...")
            # 在线程池中运行同步函数，避免阻塞事件循环
            await asyncio.to_thread(run_news_fetch_pipeline, days=1)
            logger.info("[Scheduler] News update completed. Sleeping for 30 minutes.")
        except Exception as e:
            logger.error(f"[Scheduler] News update failed: {e}")
        
        # 等待 30 分钟
        await asyncio.sleep(1800)


async def scheduled_price_update():
    """
    后台任务：实时价格更新
    每 5 分钟运行一次（K线最小粒度 15 分钟，5 分钟间隔足够）
    """
    from src.data.realtime_price_updater import get_realtime_updater
    
    # 启动延迟：等待服务器就绪后再开始，错开新闻更新
    logger.info("[Scheduler] Price update will start in 10 seconds...")
    await asyncio.sleep(10)
    
    updater = get_realtime_updater(update_interval=300)  # 5 分钟
    await updater.run()


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
    
    logger.info("[Scheduler] Background tasks started (with startup delay to ensure server readiness)")
    logger.info("[Scheduler] Price update starts in 10s, News update starts in 30s")
    logger.info("[Scheduler] Attention features will be calculated automatically after price updates")
    logger.info("[WebSocket] Real-time WebSocket endpoints available at /ws/price and /ws/attention")
    logger.info("[WebSocket] Binance WebSocket will pre-warm in 2s")
    
    yield
    
    # 关闭时取消任务
    news_task.cancel()
    price_task.cancel()
    warmup_task.cancel()
    
    # 停止 WebSocket 管理器
    try:
        ws_manager = get_ws_manager()
        if ws_manager.binance_ws and hasattr(ws_manager.binance_ws, 'stop'):
            await ws_manager.binance_ws.stop()
            logger.info("[WebSocket] Binance WebSocket stopped")
    except Exception as e:
        logger.warning(f"[WebSocket] Error stopping Binance WebSocket: {e}")
    
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
