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
from src.database.models import Symbol, get_session

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
        session = get_session()
        try:
            # 只需要检查 auto_update_price，不需要额外检查 is_active
            symbols = session.query(Symbol).filter(
                Symbol.auto_update_price == True
            ).all()
            
            return [{
                'symbol': s.symbol,
                'last_update': s.last_price_update
            } for s in symbols]
        finally:
            session.close()
    
    def update_last_price_update(self, symbol: str, timestamp: datetime):
        """更新标的的最后更新时间"""
        session = get_session()
        try:
            sym = session.query(Symbol).filter_by(symbol=symbol.upper()).first()
            if sym:
                sym.last_price_update = timestamp
                session.commit()
        finally:
            session.close()
    
    def check_data_completeness(self, symbol: str, timeframe: str, days: int = 500) -> Dict:
        """
        检查数据完整性，返回缺失的时间范围
        
        Args:
            symbol: 基础资产名
            timeframe: 时间粒度
            days: 检查的最大天数
        
        Returns:
            {'has_gaps': bool, 'missing_days': int, 'earliest_date': datetime, 'latest_date': datetime}
        """
        from src.data.db_storage import load_price_data
        import pandas as pd
        
        now = datetime.now(timezone.utc)
        earliest_expected = now - timedelta(days=days)
        
        price_df, _ = load_price_data(symbol, timeframe)
        
        if price_df is None or price_df.empty:
            return {
                'has_gaps': True,
                'missing_days': days,
                'earliest_date': None,
                'latest_date': None,
                'needs_full_fetch': True
            }
        
        # 确保 datetime 列存在
        if 'datetime' not in price_df.columns and 'timestamp' in price_df.columns:
            price_df['datetime'] = pd.to_datetime(price_df['timestamp'], unit='ms', utc=True)
        
        price_df['datetime'] = pd.to_datetime(price_df['datetime'], utc=True)
        earliest_data = price_df['datetime'].min()
        latest_data = price_df['datetime'].max()
        
        # 计算预期的数据点数量
        interval_hours = {'1d': 24, '4h': 4, '1h': 1, '15m': 0.25}
        hours_per_point = interval_hours.get(timeframe, 24)
        
        # 检查是否有足够的历史数据
        data_span_days = (latest_data - earliest_data).days
        expected_points = int(data_span_days * 24 / hours_per_point)
        actual_points = len(price_df)
        
        # 允许 5% 的容差（考虑周末、假期等）
        completeness_ratio = actual_points / max(1, expected_points)
        has_gaps = completeness_ratio < 0.95
        
        # 检查是否需要补充早期数据
        needs_backfill = earliest_data > earliest_expected + timedelta(days=7)
        
        return {
            'has_gaps': has_gaps or needs_backfill,
            'missing_days': max(0, (earliest_data - earliest_expected).days) if needs_backfill else 0,
            'earliest_date': earliest_data,
            'latest_date': latest_data,
            'needs_full_fetch': needs_backfill,
            'completeness_ratio': completeness_ratio
        }
    
    def should_check_completeness(self, symbol: str, last_update: datetime = None) -> bool:
        """
        判断是否需要进行完整性检查（避免每次都检查，节省资源）
        
        策略：
        - 首次更新（last_update 为 None）：需要检查
        - 距离上次更新超过 24 小时：需要检查
        - 其他情况：跳过检查，直接增量更新
        """
        if last_update is None:
            return True
        
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)
        
        hours_since_update = (datetime.now(timezone.utc) - last_update).total_seconds() / 3600
        
        # 只有超过 24 小时没更新才检查完整性
        return hours_since_update > 24
    
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
    
    async def update_single_symbol(self, symbol: str, last_update: datetime = None, force_full: bool = False):
        """
        更新单个标的的价格数据，支持数据完整性检查和自动补全
        
        Args:
            symbol: 基础资产名，如 'BTC'
            last_update: 最后更新时间
            force_full: 强制全量抓取
        """
        try:
            # 构造交易对名称
            symbol_pair = f"{symbol}USDT"
            
            # 判断是否需要检查完整性（节省资源：只在首次或超过24小时才检查）
            need_check = force_full or self.should_check_completeness(symbol, last_update)
            
            # 获取所有时间粒度的数据
            for timeframe in self.timeframes:
                interval_map = {'1d': '1d', '4h': '4h', '1h': '1h', '15m': '15m'}
                interval = interval_map.get(timeframe, '1d')
                
                if need_check:
                    # 检查该 timeframe 的数据完整性
                    completeness = self.check_data_completeness(symbol, timeframe)
                    
                    if force_full or completeness['needs_full_fetch'] or completeness.get('earliest_date') is None:
                        # 需要全量抓取
                        days = 500
                        logger.info(f"[Updater] {symbol} {timeframe}: needs full fetch (500 days)")
                    elif completeness['has_gaps'] and completeness.get('completeness_ratio', 1) < 0.9:
                        # 数据有较大缺口，重新抓取完整历史
                        days = 500
                        logger.info(f"[Updater] {symbol} {timeframe}: data gaps detected (ratio={completeness.get('completeness_ratio', 0):.2f}), refetching")
                    else:
                        # 数据完整，正常增量更新
                        range_info = self.calculate_fetch_range(last_update)
                        days = range_info['days']
                else:
                    # 跳过完整性检查，直接增量更新
                    range_info = self.calculate_fetch_range(last_update)
                    days = range_info['days']
                
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
                elif days > 1:
                    logger.warning(f"[Updater]   {symbol} {timeframe}: no data returned for {days} days")
            
            # 更新最后更新时间
            self.update_last_price_update(symbol, datetime.now(timezone.utc))
            logger.info(f"[Updater] ✅ {symbol} price update completed")
            
        except Exception as e:
            logger.error(f"[Updater] Failed to update {symbol}: {e}")
    
    async def update_all_symbols(self, force_check_completeness: bool = False):
        """
        更新所有配置为自动更新的标的，并在价格更新后立即计算 Attention Features
        
        Args:
            force_check_completeness: 强制检查所有 timeframe 的数据完整性
        """
        from src.features.attention_features import process_attention_features
        
        symbols = self.get_auto_update_symbols()
        
        if not symbols:
            logger.info("[Updater] No symbols configured for auto-update")
            return
        
        logger.info(f"[Updater] Updating {len(symbols)} symbols...")
        
        # 顺序更新（避免并发过多触发限流）
        for sym_info in symbols:
            symbol = sym_info['symbol']
            logger.info(f"[Updater] Processing {symbol}...")
            
            # 1. 更新价格数据（会自动检查数据完整性）
            await self.update_single_symbol(symbol, sym_info['last_update'])
            
            # 2. 立即计算 Attention Features
            try:
                logger.info(f"[Updater] Calculating attention features for {symbol}...")
                await asyncio.to_thread(process_attention_features, symbol, freq='D', save_to_db=True)
                logger.info(f"[Updater] ✅ Attention features updated for {symbol}")
            except Exception as e:
                logger.error(f"[Updater] ❌ Failed to calculate attention for {symbol}: {e}")
        
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
