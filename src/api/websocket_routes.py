#!/usr/bin/env python3
"""
WebSocket 路由与连接管理
为前端提供实时价格和注意力数据推送

设计原则：
- WebSocket 是可选的增强功能，不影响核心数据流
- 如果 Binance WebSocket 连接失败，不会阻塞主服务
- 前端可以同时使用 WebSocket 和 REST API，WebSocket 用于实时更新，REST API 用于历史数据
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# 延迟导入，避免循环依赖和启动时错误
_binance_ws_manager = None


def _get_binance_ws_manager():
    """延迟获取 Binance WebSocket 管理器，避免启动时错误"""
    global _binance_ws_manager
    if _binance_ws_manager is None:
        try:
            from src.data.binance_websocket import get_binance_ws_manager
            _binance_ws_manager = get_binance_ws_manager()
        except Exception as e:
            logger.warning(f"[WS] Failed to initialize Binance WebSocket: {e}")
            _binance_ws_manager = None
    return _binance_ws_manager


class ConnectionManager:
    """
    WebSocket 连接管理器
    
    管理所有客户端连接，支持：
    - 按 symbol 分组的订阅
    - 广播消息到所有订阅者
    - 连接健康检查
    - 优雅降级（Binance WS 不可用时仍可接受客户端连接）
    """
    
    def __init__(self):
        # symbol -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> set of symbols
        self.client_subscriptions: Dict[WebSocket, Set[str]] = {}
        # Binance WS 管理器（延迟初始化）
        self.binance_ws = None
        self._binance_subscriptions: Set[str] = set()
        self._lock = asyncio.Lock()
        self._binance_init_failed = False  # 标记 Binance 初始化是否失败
    
    async def connect(self, websocket: WebSocket):
        """接受新连接"""
        await websocket.accept()
        self.client_subscriptions[websocket] = set()
        logger.info(f"[WS] Client connected. Total clients: {len(self.client_subscriptions)}")
    
    async def disconnect(self, websocket: WebSocket):
        """处理断开连接"""
        if websocket in self.client_subscriptions:
            # 从所有订阅组中移除
            symbols = self.client_subscriptions[websocket]
            for symbol in symbols:
                if symbol in self.active_connections:
                    self.active_connections[symbol].discard(websocket)
                    # 如果没有订阅者了，清理
                    if not self.active_connections[symbol]:
                        del self.active_connections[symbol]
            
            del self.client_subscriptions[websocket]
        
        logger.info(f"[WS] Client disconnected. Total clients: {len(self.client_subscriptions)}")
    
    async def subscribe(self, websocket: WebSocket, symbol: str):
        """订阅 symbol 的实时数据"""
        symbol = symbol.upper()
        
        # 添加到连接组
        if symbol not in self.active_connections:
            self.active_connections[symbol] = set()
        self.active_connections[symbol].add(websocket)
        
        # 记录客户端订阅
        if websocket in self.client_subscriptions:
            self.client_subscriptions[websocket].add(symbol)
        
        logger.info(f"[WS] Client subscribed to {symbol}. Subscribers: {len(self.active_connections.get(symbol, set()))}")
        
        # 启动 Binance WebSocket 订阅（如果还没有）
        await self._ensure_binance_subscription(symbol)
    
    async def unsubscribe(self, websocket: WebSocket, symbol: str):
        """取消订阅"""
        symbol = symbol.upper()
        
        if symbol in self.active_connections:
            self.active_connections[symbol].discard(websocket)
        
        if websocket in self.client_subscriptions:
            self.client_subscriptions[websocket].discard(symbol)
        
        logger.info(f"[WS] Client unsubscribed from {symbol}")
    
    async def broadcast_to_symbol(self, symbol: str, message: dict):
        """向订阅某 symbol 的所有客户端广播消息"""
        symbol = symbol.upper()
        
        if symbol not in self.active_connections:
            return
        
        disconnected = set()
        for websocket in self.active_connections[symbol]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"[WS] Failed to send to client: {e}")
                disconnected.add(websocket)
        
        # 清理断开的连接
        for ws in disconnected:
            await self.disconnect(ws)
    
    async def broadcast_all(self, message: dict):
        """向所有连接的客户端广播"""
        disconnected = set()
        for websocket in self.client_subscriptions.keys():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.warning(f"[WS] Failed to broadcast: {e}")
                disconnected.add(websocket)
        
        for ws in disconnected:
            await self.disconnect(ws)
    
    async def _ensure_binance_subscription(self, symbol: str):
        """
        确保 Binance WebSocket 已订阅该交易对
        
        优雅降级：如果 Binance WS 不可用，仅记录警告，不阻塞客户端连接
        """
        # 如果之前初始化失败，跳过重试（避免重复错误日志）
        if self._binance_init_failed:
            return
            
        async with self._lock:
            if self.binance_ws is None:
                self.binance_ws = _get_binance_ws_manager()
                if self.binance_ws is None:
                    self._binance_init_failed = True
                    logger.warning("[WS] Binance WebSocket not available, real-time price push disabled")
                    return
                    
                # 启动 Binance WS（如果还没运行）
                try:
                    if not self.binance_ws.is_running:
                        await self.binance_ws.start()
                except Exception as e:
                    logger.error(f"[WS] Failed to start Binance WebSocket: {e}")
                    self._binance_init_failed = True
                    return
            
            # 订阅交易对（使用 1m K 线）
            trading_pair = f"{symbol}USDT"
            if trading_pair not in self._binance_subscriptions:
                self._binance_subscriptions.add(trading_pair)
                
                # 注册回调 - 使用默认参数捕获当前 symbol 值
                async def on_kline(data: dict, sym: str = symbol):
                    logger.debug(f"[WS] Received kline for {sym}: close={data.get('close')}")
                    await self._on_binance_kline(sym, data)
                
                try:
                    await self.binance_ws.subscribe(trading_pair, "1m", on_kline)
                    logger.info(f"[WS] Binance subscription added for {trading_pair}")
                except Exception as e:
                    logger.error(f"[WS] Failed to subscribe to {trading_pair}: {e}")
                    self._binance_subscriptions.discard(trading_pair)
    
    async def _on_binance_kline(self, symbol: str, data: dict):
        """处理 Binance K 线数据，广播给订阅者"""
        logger.debug(f"[WS] Broadcasting price_update for {symbol} to {len(self.active_connections.get(symbol, set()))} clients")
        
        # 转换为前端格式
        message = {
            "type": "price_update",
            "symbol": symbol,
            "data": {
                "timestamp": data.get("timestamp"),
                "datetime": datetime.fromtimestamp(
                    data.get("timestamp", 0) / 1000, tz=timezone.utc
                ).isoformat(),
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "close": data.get("close"),
                "volume": data.get("volume"),
                "is_closed": data.get("is_closed", False),
            }
        }
        
        await self.broadcast_to_symbol(symbol, message)
    
    def get_stats(self) -> dict:
        """获取连接统计信息"""
        binance_status = "not_initialized"
        if self._binance_init_failed:
            binance_status = "init_failed"
        elif self.binance_ws is not None:
            binance_status = "connected" if self.binance_ws.is_running else "disconnected"
            
        return {
            "total_clients": len(self.client_subscriptions),
            "subscriptions_by_symbol": {
                symbol: len(clients) 
                for symbol, clients in self.active_connections.items()
            },
            "binance_status": binance_status,
            "binance_connected": self.binance_ws is not None and self.binance_ws.is_running,
            "binance_subscriptions": list(self._binance_subscriptions),
        }


# 全局连接管理器
manager = ConnectionManager()


async def websocket_price_endpoint(websocket: WebSocket):
    """
    价格数据 WebSocket 端点
    
    协议：
    客户端发送:
        {"action": "subscribe", "symbols": ["BTC", "ETH"]}
        {"action": "unsubscribe", "symbols": ["BTC"]}
        {"action": "ping"}
    
    服务端推送:
        {"type": "price_update", "symbol": "BTC", "data": {...}}
        {"type": "subscribed", "symbols": ["BTC", "ETH"]}
        {"type": "pong"}
        {"type": "error", "message": "..."}
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            action = data.get("action", "")
            
            if action == "subscribe":
                symbols = data.get("symbols", [])
                for symbol in symbols:
                    await manager.subscribe(websocket, symbol)
                await websocket.send_json({
                    "type": "subscribed",
                    "symbols": symbols
                })
            
            elif action == "unsubscribe":
                symbols = data.get("symbols", [])
                for symbol in symbols:
                    await manager.unsubscribe(websocket, symbol)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "symbols": symbols
                })
            
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
            
            elif action == "get_stats":
                stats = manager.get_stats()
                await websocket.send_json({
                    "type": "stats",
                    "data": stats
                })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}"
                })
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[WS] Error in price endpoint: {e}")
        await manager.disconnect(websocket)


async def websocket_attention_endpoint(websocket: WebSocket):
    """
    注意力数据 WebSocket 端点
    
    推送注意力分数变化、注意力事件等
    
    协议：
    客户端发送:
        {"action": "subscribe", "symbols": ["BTC", "ETH"]}
    
    服务端推送:
        {"type": "attention_update", "symbol": "BTC", "data": {...}}
        {"type": "attention_event", "symbol": "BTC", "event": {...}}
    """
    await manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")
            
            if action == "subscribe":
                symbols = data.get("symbols", [])
                # 注意力数据复用同一个订阅管理
                for symbol in symbols:
                    await manager.subscribe(websocket, symbol)
                await websocket.send_json({
                    "type": "subscribed",
                    "symbols": symbols
                })
            
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[WS] Error in attention endpoint: {e}")
        await manager.disconnect(websocket)


async def broadcast_attention_event(symbol: str, event_data: dict):
    """
    广播注意力事件（供其他模块调用）
    
    Args:
        symbol: 代币符号
        event_data: 事件数据
    """
    message = {
        "type": "attention_event",
        "symbol": symbol,
        "event": event_data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await manager.broadcast_to_symbol(symbol, message)


async def broadcast_attention_update(symbol: str, attention_data: dict):
    """
    广播注意力分数更新
    
    Args:
        symbol: 代币符号
        attention_data: 注意力数据
    """
    message = {
        "type": "attention_update",
        "symbol": symbol,
        "data": attention_data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await manager.broadcast_to_symbol(symbol, message)


def get_ws_manager() -> ConnectionManager:
    """获取全局 WebSocket 管理器"""
    return manager
