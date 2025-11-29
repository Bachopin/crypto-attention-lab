#!/usr/bin/env python3
"""
实时价格更新服务
支持配置自动更新的标的列表，定期（1-2分钟）抓取最新价格数据
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from src.data.price_fetcher_binance import BinancePriceFetcher
from src.data.db_storage import get_db, save_price_data
from src.database.models import Symbol

logger = logging.getLogger(__name__)


class RealtimePriceUpdater:
    """实时价格更新器"""
    
    def __init__(self, update_interval: int = 120):
        """
        Args:
            update_interval: 更新间隔（秒），默认 120 秒（2分钟）
        """
        self.update_interval = update_interval
        self.fetcher = BinancePriceFetcher()
        self.db = get_db()
        self.is_running = False
        self.timeframes = ['1d', '4h', '1h', '15m']
    
    def get_auto_update_symbols(self) -> List[Dict]:
        """
        获取需要自动更新的标的列表
        Returns:
            [{'symbol': 'BTC', 'last_update': datetime}, ...]
        """
        from src.database.models import get_session
        
        session = get_session()
        try:
            symbols = session.query(Symbol).filter_by(
                auto_update_price=True,
                is_active=True
            ).all()
            
            result = [{
                'symbol': s.symbol,
                'last_update': s.last_price_update
            } for s in symbols]
            
            return result
        finally:
            session.close()
    
    def update_last_price_update(self, symbol: str, timestamp: datetime):
        """更新标的的最后更新时间"""
        from src.database.models import get_session
        
        session = get_session()
        try:
            sym = session.query(Symbol).filter_by(symbol=symbol.upper()).first()
            if sym:
                sym.last_price_update = timestamp
                session.commit()
        finally:
            session.close()
    
    def calculate_fetch_range(self, last_update: datetime = None) -> Dict:
        """
        计算需要抓取的时间范围
        
        Args:
            last_update: 最后一次更新时间
        
        Returns:
            {'start': datetime, 'end': datetime, 'days': int}
        """
        now = datetime.now(timezone.utc)
        
        if last_update is None:
            # 首次抓取，拉取 500 天历史数据（约 1.4 年）
            start = now - timedelta(days=500)
            days = 500
        else:
            # 确保 last_update 是 timezone-aware
            if last_update.tzinfo is None:
                last_update = last_update.replace(tzinfo=timezone.utc)
            # 增量更新，从上次更新时间开始
            start = last_update
            days = max(1, (now - last_update).days + 1)
        
        return {
            'start': start,
            'end': now,
            'days': days
        }
    
    async def update_single_symbol(self, symbol: str, last_update: datetime = None):
        """
        更新单个标的的价格数据
        
        Args:
            symbol: 基础资产名，如 'BTC'
            last_update: 最后更新时间
        """
        try:
            # 计算抓取范围
            range_info = self.calculate_fetch_range(last_update)
            days = range_info['days']
            
            logger.info(f"[Updater] Updating {symbol}, fetching {days} days of data...")
            
            # 构造交易对名称
            symbol_pair = f"{symbol}USDT"
            
            # 获取所有时间粒度的数据
            for timeframe in self.timeframes:
                interval_map = {'1d': '1d', '4h': '4h', '1h': '1h', '15m': '15m'}
                interval = interval_map.get(timeframe, '1d')
                
                # 抓取数据
                klines = self.fetcher.fetch_historical_klines_batch(
                    symbol_pair,
                    interval,
                    days=days
                )
                
                if klines:
                    # 保存到数据库
                    save_price_data(symbol, timeframe, klines)
                    logger.info(f"[Updater]   {symbol} {timeframe}: {len(klines)} records saved")
            
            # 更新最后更新时间
            self.update_last_price_update(symbol, datetime.now(timezone.utc))
            
        except Exception as e:
            logger.error(f"[Updater] Failed to update {symbol}: {e}")
    
    async def update_all_symbols(self):
        """更新所有配置为自动更新的标的"""
        symbols = self.get_auto_update_symbols()
        
        if not symbols:
            logger.info("[Updater] No symbols configured for auto-update")
            return
        
        logger.info(f"[Updater] Updating {len(symbols)} symbols...")
        
        # 顺序更新（避免并发过多触发限流）
        for sym_info in symbols:
            await self.update_single_symbol(
                sym_info['symbol'],
                sym_info['last_update']
            )
        
        logger.info("[Updater] Update cycle completed")
    
    async def run(self):
        """运行定时更新循环"""
        self.is_running = True
        logger.info(f"[Updater] Started (interval: {self.update_interval}s)")
        
        while self.is_running:
            try:
                await self.update_all_symbols()
            except Exception as e:
                logger.error(f"[Updater] Update cycle error: {e}")
            
            # 等待下一个周期
            await asyncio.sleep(self.update_interval)
    
    def stop(self):
        """停止更新"""
        self.is_running = False
        logger.info("[Updater] Stopped")


# 全局实例
_updater_instance = None


def get_realtime_updater(update_interval: int = 120) -> RealtimePriceUpdater:
    """获取全局实时更新器实例"""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = RealtimePriceUpdater(update_interval)
    return _updater_instance
