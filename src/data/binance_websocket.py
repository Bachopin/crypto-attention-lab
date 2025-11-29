#!/usr/bin/env python3
"""
Binance WebSocket 实时数据服务
连接 Binance WebSocket API 获取毫秒级实时价格数据
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class BinanceWebSocketManager:
    """
    Binance WebSocket 连接管理器
    
    功能：
    - 连接 Binance WebSocket 流
    - 订阅多个交易对的实时 K 线数据
    - 自动重连机制
    - 数据回调分发
    """
    
    # Binance WebSocket 端点
    SPOT_WS_URL = "wss://stream.binance.com:9443/ws"
    FUTURES_WS_URL = "wss://fstream.binance.com/ws"
    
    def __init__(self, use_futures: bool = False):
        """
        Args:
            use_futures: 是否使用合约 WebSocket（默认现货）
        """
        self.ws_url = self.FUTURES_WS_URL if use_futures else self.SPOT_WS_URL
        self.use_futures = use_futures
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.subscriptions: Set[str] = set()  # 已订阅的流
        self.callbacks: Dict[str, List[Callable]] = {}  # stream -> [callbacks]
        self.is_running = False
        self.reconnect_delay = 1  # 初始重连延迟（秒）
        self.max_reconnect_delay = 60  # 最大重连延迟
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._tasks: List[asyncio.Task] = []
    
    def _get_stream_name(self, symbol: str, interval: str = "1m") -> str:
        """
        构建流名称
        
        Args:
            symbol: 交易对，如 BTCUSDT
            interval: K 线间隔，如 1m, 5m, 15m, 1h, 4h, 1d
        
        Returns:
            流名称，如 btcusdt@kline_1m
        """
        return f"{symbol.lower()}@kline_{interval}"
    
    def _get_trade_stream_name(self, symbol: str) -> str:
        """获取逐笔成交流名称"""
        return f"{symbol.lower()}@trade"
    
    def _get_ticker_stream_name(self, symbol: str) -> str:
        """获取 24h Ticker 流名称"""
        return f"{symbol.lower()}@ticker"
    
    async def connect(self):
        """建立 WebSocket 连接"""
        try:
            logger.info(f"[BinanceWS] Connecting to {self.ws_url}...")
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            self.reconnect_delay = 1  # 重置重连延迟
            logger.info("[BinanceWS] Connected successfully")
            return True
        except Exception as e:
            logger.error(f"[BinanceWS] Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        self.is_running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        logger.info("[BinanceWS] Disconnected")
    
    async def subscribe(self, symbol: str, interval: str = "1m", callback: Optional[Callable] = None):
        """
        订阅 K 线数据流
        
        Args:
            symbol: 交易对，如 BTCUSDT
            interval: K 线间隔
            callback: 数据回调函数 (data: dict) -> None
        """
        stream = self._get_stream_name(symbol, interval)
        
        if stream not in self.subscriptions:
            self.subscriptions.add(stream)
            
            # 发送订阅请求
            if self.websocket:
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": [stream],
                    "id": len(self.subscriptions)
                }
                await self.websocket.send(json.dumps(subscribe_msg))
                logger.info(f"[BinanceWS] Subscribed to {stream}")
        
        # 注册回调
        if callback:
            if stream not in self.callbacks:
                self.callbacks[stream] = []
            self.callbacks[stream].append(callback)
    
    async def subscribe_ticker(self, symbol: str, callback: Optional[Callable] = None):
        """订阅 24h Ticker 数据"""
        stream = self._get_ticker_stream_name(symbol)
        
        if stream not in self.subscriptions:
            self.subscriptions.add(stream)
            
            if self.websocket:
                subscribe_msg = {
                    "method": "SUBSCRIBE",
                    "params": [stream],
                    "id": len(self.subscriptions)
                }
                await self.websocket.send(json.dumps(subscribe_msg))
                logger.info(f"[BinanceWS] Subscribed to ticker {stream}")
        
        if callback:
            if stream not in self.callbacks:
                self.callbacks[stream] = []
            self.callbacks[stream].append(callback)
    
    async def unsubscribe(self, symbol: str, interval: str = "1m"):
        """取消订阅"""
        stream = self._get_stream_name(symbol, interval)
        
        if stream in self.subscriptions:
            self.subscriptions.remove(stream)
            
            if self.websocket:
                unsubscribe_msg = {
                    "method": "UNSUBSCRIBE",
                    "params": [stream],
                    "id": 9999
                }
                await self.websocket.send(json.dumps(unsubscribe_msg))
                logger.info(f"[BinanceWS] Unsubscribed from {stream}")
            
            # 移除回调
            if stream in self.callbacks:
                del self.callbacks[stream]
    
    async def _handle_message(self, message: str):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            
            # 跳过订阅确认消息
            if "result" in data:
                return
            
            # 获取流名称
            stream = data.get("s", "").lower()  # 从 symbol 构建
            event_type = data.get("e", "")
            
            if event_type == "kline":
                # K 线数据
                kline = data.get("k", {})
                symbol = kline.get("s", "").lower()
                interval = kline.get("i", "1m")
                stream = f"{symbol}@kline_{interval}"
                
                # 解析 K 线数据
                parsed_data = {
                    "type": "kline",
                    "symbol": kline.get("s"),
                    "interval": interval,
                    "timestamp": kline.get("t"),  # 开盘时间
                    "open": float(kline.get("o", 0)),
                    "high": float(kline.get("h", 0)),
                    "low": float(kline.get("l", 0)),
                    "close": float(kline.get("c", 0)),
                    "volume": float(kline.get("v", 0)),
                    "is_closed": kline.get("x", False),  # K 线是否已收盘
                    "trades": int(kline.get("n", 0)),  # 成交笔数
                }
                
                # 调用回调
                if stream in self.callbacks:
                    for callback in self.callbacks[stream]:
                        try:
                            await callback(parsed_data) if asyncio.iscoroutinefunction(callback) else callback(parsed_data)
                        except Exception as e:
                            logger.error(f"[BinanceWS] Callback error: {e}")
            
            elif event_type == "24hrTicker":
                # Ticker 数据
                symbol = data.get("s", "").lower()
                stream = f"{symbol}@ticker"
                
                parsed_data = {
                    "type": "ticker",
                    "symbol": data.get("s"),
                    "price_change": float(data.get("p", 0)),
                    "price_change_percent": float(data.get("P", 0)),
                    "last_price": float(data.get("c", 0)),
                    "high_24h": float(data.get("h", 0)),
                    "low_24h": float(data.get("l", 0)),
                    "volume_24h": float(data.get("v", 0)),
                    "quote_volume_24h": float(data.get("q", 0)),
                }
                
                if stream in self.callbacks:
                    for callback in self.callbacks[stream]:
                        try:
                            await callback(parsed_data) if asyncio.iscoroutinefunction(callback) else callback(parsed_data)
                        except Exception as e:
                            logger.error(f"[BinanceWS] Callback error: {e}")
                            
        except json.JSONDecodeError as e:
            logger.warning(f"[BinanceWS] Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"[BinanceWS] Message handling error: {e}")
    
    async def _reconnect(self):
        """重连逻辑"""
        while self.is_running:
            logger.info(f"[BinanceWS] Reconnecting in {self.reconnect_delay}s...")
            await asyncio.sleep(self.reconnect_delay)
            
            if await self.connect():
                # 重新订阅所有流
                if self.subscriptions:
                    subscribe_msg = {
                        "method": "SUBSCRIBE",
                        "params": list(self.subscriptions),
                        "id": 1
                    }
                    await self.websocket.send(json.dumps(subscribe_msg))
                    logger.info(f"[BinanceWS] Resubscribed to {len(self.subscriptions)} streams")
                return
            
            # 指数退避
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    async def run(self):
        """运行 WebSocket 客户端"""
        self.is_running = True
        
        while self.is_running:
            if not self.websocket or self.websocket.closed:
                if not await self.connect():
                    await self._reconnect()
                    continue
            
            try:
                async for message in self.websocket:
                    if not self.is_running:
                        break
                    await self._handle_message(message)
                    
            except ConnectionClosed as e:
                logger.warning(f"[BinanceWS] Connection closed: {e}")
                if self.is_running:
                    await self._reconnect()
            except Exception as e:
                logger.error(f"[BinanceWS] Error: {e}")
                if self.is_running:
                    await self._reconnect()
    
    async def start(self):
        """启动 WebSocket 服务（后台任务）"""
        task = asyncio.create_task(self.run())
        self._tasks.append(task)
        return task
    
    async def stop(self):
        """停止 WebSocket 服务"""
        self.is_running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        await self.disconnect()


# 全局实例
_binance_ws_manager: Optional[BinanceWebSocketManager] = None


def get_binance_ws_manager() -> BinanceWebSocketManager:
    """获取全局 Binance WebSocket 管理器"""
    global _binance_ws_manager
    if _binance_ws_manager is None:
        _binance_ws_manager = BinanceWebSocketManager()
    return _binance_ws_manager


async def init_binance_websocket():
    """初始化并启动 Binance WebSocket"""
    manager = get_binance_ws_manager()
    await manager.start()
    return manager
