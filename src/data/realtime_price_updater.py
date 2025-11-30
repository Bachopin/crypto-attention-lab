#!/usr/bin/env python3
"""
实时价格更新服务

更新策略：
- 价格更新：每 10 分钟轮询所有标的（间隔可配置）
- 多标的错峰：在更新周期内均匀分布各标的的更新时间
- 特征值更新：价格更新后触发，带 1 小时冷却期
- Google Trends 更新：特征值更新时触发，带 12 小时冷却期

级联更新链：
价格更新完成 → 检查特征值冷却期 → 检查 Google Trends 冷却期
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from src.data.price_fetcher_binance import BinancePriceFetcher
from src.data.db_storage import get_db, save_price_data
from src.database.models import Symbol, get_session
from src.config.settings import (
    PRICE_UPDATE_INTERVAL,
    FEATURE_UPDATE_COOLDOWN,
    GOOGLE_TRENDS_COOLDOWN,
)

logger = logging.getLogger(__name__)


class RealtimePriceUpdater:
    """实时价格更新器 - 支持错峰更新和级联触发"""
    
    def __init__(self, update_interval: int = None):
        """
        Args:
            update_interval: 更新间隔（秒），默认使用配置文件中的 PRICE_UPDATE_INTERVAL
        """
        self.update_interval = update_interval or PRICE_UPDATE_INTERVAL
        self.fetcher = BinancePriceFetcher()
        self.db = get_db()
        self.is_running = False
        self.timeframes = ['1d', '4h', '1h', '15m']
    
    def get_auto_update_symbols(self) -> List[Dict]:
        """
        获取需要自动更新的标的列表，包含所有更新时间戳
        Returns:
            [{'symbol': 'BTC', 'last_price_update': datetime, 
              'last_attention_update': datetime, 'last_google_trends_update': datetime}, ...]
        """
        session = get_session()
        try:
            symbols = session.query(Symbol).filter(
                Symbol.auto_update_price == True
            ).all()
            
            return [{
                'symbol': s.symbol,
                'last_update': s.last_price_update,  # 兼容旧代码
                'last_price_update': s.last_price_update,
                'last_attention_update': getattr(s, 'last_attention_update', None),
                'last_google_trends_update': getattr(s, 'last_google_trends_update', None),
            } for s in symbols]
        finally:
            session.close()
    
    def update_symbol_timestamps(
        self, 
        symbol: str, 
        price_update: Optional[datetime] = None,
        attention_update: Optional[datetime] = None,
        google_trends_update: Optional[datetime] = None
    ):
        """更新标的的各类更新时间戳"""
        session = get_session()
        try:
            sym = session.query(Symbol).filter_by(symbol=symbol.upper()).first()
            if sym:
                if price_update:
                    sym.last_price_update = price_update
                if attention_update:
                    sym.last_attention_update = attention_update
                if google_trends_update:
                    sym.last_google_trends_update = google_trends_update
                session.commit()
        finally:
            session.close()
    
    def update_last_price_update(self, symbol: str, timestamp: datetime):
        """更新标的的最后更新时间（兼容旧接口）"""
        self.update_symbol_timestamps(symbol, price_update=timestamp)
    
    def _ensure_aware_datetime(self, dt: Optional[datetime]) -> Optional[datetime]:
        """确保 datetime 是 timezone-aware 的"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # 假设 naive datetime 是 UTC
            return dt.replace(tzinfo=timezone.utc)
        return dt
    
    def should_update_attention(self, last_update: Optional[datetime]) -> bool:
        """检查是否应该更新特征值（冷却期检查）"""
        if last_update is None:
            return True
        now = datetime.now(timezone.utc)
        last_update = self._ensure_aware_datetime(last_update)
        elapsed = (now - last_update).total_seconds()
        return elapsed >= FEATURE_UPDATE_COOLDOWN
    
    def should_update_google_trends(self, last_update: Optional[datetime]) -> bool:
        """检查是否应该更新 Google Trends（冷却期检查）"""
        if last_update is None:
            return True
        now = datetime.now(timezone.utc)
        last_update = self._ensure_aware_datetime(last_update)
        elapsed = (now - last_update).total_seconds()
        return elapsed >= GOOGLE_TRENDS_COOLDOWN
    
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
        
        注意：即使需要检查，也应该只抓取缺失的数据，而不是每次都全量抓取
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
                    
                    if force_full:
                        # 强制全量抓取（仅在用户手动触发时使用）
                        days = 500
                        logger.info(f"[Updater] {symbol} {timeframe}: forced full fetch (500 days)")
                    elif completeness.get('earliest_date') is None:
                        # 首次抓取该 symbol/timeframe，需要全量
                        days = 500
                        logger.info(f"[Updater] {symbol} {timeframe}: initial fetch (500 days)")
                    elif completeness['needs_full_fetch'] and completeness.get('completeness_ratio', 1) < 0.5:
                        # 数据严重缺失（<50%），才考虑全量抓取
                        days = 500
                        logger.info(f"[Updater] {symbol} {timeframe}: severe data gaps (ratio={completeness.get('completeness_ratio', 0):.2f}), refetching")
                    else:
                        # 数据基本完整，正常增量更新（只抓最近几天）
                        range_info = self.calculate_fetch_range(last_update)
                        days = min(range_info['days'], 7)  # 增量更新最多 7 天
                else:
                    # 跳过完整性检查，直接增量更新（常规定时更新）
                    range_info = self.calculate_fetch_range(last_update)
                    days = min(range_info['days'], 3)  # 常规更新最多 3 天
                
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
        更新所有配置为自动更新的标的
        
        更新策略：
        1. 多标的错峰更新：在更新周期内均匀分布各标的的更新时间
        2. 级联更新：价格 → 特征值（冷却期过滤）→ Google Trends（冷却期过滤）
        
        Args:
            force_check_completeness: 强制检查所有 timeframe 的数据完整性
        """
        from src.services.attention_service import AttentionService
        
        symbols = self.get_auto_update_symbols()
        
        if not symbols:
            logger.info("[Updater] No symbols configured for auto-update")
            return
        
        num_symbols = len(symbols)
        logger.info(f"[Updater] Updating {num_symbols} symbols (interval: {self.update_interval}s)...")
        
        # 计算每个标的之间的间隔时间（错峰更新）
        # 预留 20% 时间作为缓冲
        per_symbol_interval = (self.update_interval * 0.8) / max(num_symbols, 1)
        
        for idx, sym_info in enumerate(symbols):
            symbol = sym_info['symbol']
            last_attention = sym_info.get('last_attention_update')
            last_google = sym_info.get('last_google_trends_update')
            
            logger.info(f"[Updater] [{idx+1}/{num_symbols}] Processing {symbol}...")
            
            # 1. 更新价格数据
            await self.update_single_symbol(symbol, sym_info['last_update'])
            
            # 2. 检查是否需要更新特征值（冷却期过滤）
            if self.should_update_attention(last_attention):
                try:
                    # 检查是否需要更新 Google Trends（在特征值计算前决定）
                    need_google_update = self.should_update_google_trends(last_google)
                    
                    logger.info(f"[Updater] Calculating attention features for {symbol} (Google Trends: {'yes' if need_google_update else 'skip'})...")
                    
                    # 3. 计算特征值（内部会决定是否调用 Google Trends）
                    attention_df = await asyncio.to_thread(
                        AttentionService.update_attention_features_incremental,
                        symbol,
                        freq='D',
                        save_to_db=True,
                        force_google_trends=need_google_update
                    )
                    
                    # 更新时间戳
                    now = datetime.now(timezone.utc)
                    self.update_symbol_timestamps(
                        symbol,
                        attention_update=now,
                        google_trends_update=now if need_google_update else None
                    )
                    
                    logger.info(f"[Updater] ✅ Attention features updated for {symbol}")
                    
                    # 4. 广播 WebSocket 更新
                    if attention_df is not None and not attention_df.empty:
                        await self._broadcast_attention_update(symbol, attention_df)
                        
                except Exception as e:
                    logger.error(f"[Updater] ❌ Failed to calculate attention for {symbol}: {e}")
            else:
                # 确保 last_attention 是 timezone-aware
                last_attention_aware = self._ensure_aware_datetime(last_attention)
                cooldown_remaining = FEATURE_UPDATE_COOLDOWN - (datetime.now(timezone.utc) - last_attention_aware).total_seconds() if last_attention_aware else 0
                logger.debug(f"[Updater] Skipping attention for {symbol} (cooldown: {cooldown_remaining/60:.0f}min remaining)")
            
            # 错峰延迟（最后一个标的不需要等待）
            if idx < num_symbols - 1 and per_symbol_interval > 1:
                # 添加少量随机性避免完全同步
                jitter = random.uniform(0, per_symbol_interval * 0.1)
                await asyncio.sleep(per_symbol_interval + jitter)
        
        logger.info("[Updater] Update cycle completed")
    
    async def _broadcast_attention_update(self, symbol: str, attention_df):
        """
        通过 WebSocket 广播 Attention 更新
        
        仅在有 WebSocket 订阅者时才广播，避免不必要的开销
        """
        try:
            from src.api.websocket_routes import broadcast_attention_update, get_ws_manager
            
            ws_manager = get_ws_manager()
            # 检查是否有订阅者
            if symbol.upper() not in ws_manager.active_connections:
                return
            
            # 获取最新一条数据
            latest = attention_df.iloc[-1]
            attention_data = {
                "datetime": str(latest.get('datetime', '')),
                "attention_score": float(latest.get('attention_score', 0)),
                "news_count": int(latest.get('news_count', 0)),
                "composite_attention_score": float(latest.get('composite_attention_score', 0) or 0),
                "composite_attention_zscore": float(latest.get('composite_attention_zscore', 0) or 0),
            }
            
            await broadcast_attention_update(symbol, attention_data)
            logger.debug(f"[Updater] Broadcasted attention update for {symbol}")
            
        except ImportError:
            # WebSocket 模块未加载，跳过广播
            pass
        except Exception as e:
            # 广播失败不应影响主流程
            logger.warning(f"[Updater] Failed to broadcast attention update for {symbol}: {e}")
    
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


def get_realtime_updater(update_interval: int = None) -> RealtimePriceUpdater:
    """获取全局实时更新器实例（默认使用配置文件中的间隔）"""
    global _updater_instance
    if _updater_instance is None:
        _updater_instance = RealtimePriceUpdater(update_interval)
    return _updater_instance
