#!/usr/bin/env python3
"""
Binance Price Fetcher - 无需 API Key 的公共行情接口
支持批量获取 USDT 计价交易对的 K 线数据
支持现货（Spot）和合约（Futures）两个市场
"""
import requests
import pandas as pd
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Binance API endpoints
SPOT_BASE_URL = "https://api.binance.com/api/v3"
FUTURES_BASE_URL = "https://fapi.binance.com/fapi/v1"
RATE_LIMIT_DELAY = 0.1  # 每个请求间隔 100ms，避免触发限流


class BinancePriceFetcher:
    """币安价格数据获取器 - 支持现货和合约"""
    
    def __init__(self, rate_limit_delay: float = RATE_LIMIT_DELAY):
        self.spot_url = SPOT_BASE_URL
        self.futures_url = FUTURES_BASE_URL
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})
        # 缓存：记录交易对的市场类型
        self._futures_symbols: set = set()
        self._spot_symbols: set = set()
        self._unavailable_symbols: set = set()
    
    def get_all_usdt_pairs(self) -> List[str]:
        """
        获取所有 USDT 计价的活跃交易对（现货）
        Returns: ['BTCUSDT', 'ETHUSDT', ...]
        """
        try:
            url = f"{self.spot_url}/exchangeInfo"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            pairs = [
                s['symbol']
                for s in data.get('symbols', [])
                if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING'
            ]
            
            logger.info(f"[Binance] Found {len(pairs)} active USDT pairs")
            return pairs
        except Exception as e:
            logger.error(f"[Binance] Failed to fetch exchange info: {e}")
            return []
    
    def _check_symbol_availability(self, symbol: str) -> str:
        """
        检查交易对在哪个市场可用（带缓存）
        Returns: 'spot', 'futures', or 'none'
        """
        # 检查缓存
        if symbol in self._spot_symbols:
            return 'spot'
        if symbol in self._futures_symbols:
            return 'futures'
        if symbol in self._unavailable_symbols:
            return 'none'
        
        # 先检查现货
        try:
            url = f"{self.spot_url}/klines"
            params = {'symbol': symbol, 'interval': '1d', 'limit': 1}
            resp = self.session.get(url, params=params, timeout=5)
            if resp.status_code == 200 and resp.json():
                self._spot_symbols.add(symbol)
                logger.info(f"[Binance] {symbol} available on Spot")
                return 'spot'
        except:
            pass
        
        # 再检查合约
        try:
            url = f"{self.futures_url}/klines"
            params = {'symbol': symbol, 'interval': '1d', 'limit': 1}
            resp = self.session.get(url, params=params, timeout=5)
            if resp.status_code == 200 and resp.json():
                self._futures_symbols.add(symbol)
                logger.info(f"[Binance] {symbol} available on Futures")
                return 'futures'
        except:
            pass
        
        self._unavailable_symbols.add(symbol)
        return 'none'
    
    def get_base_assets_from_pairs(self, pairs: List[str]) -> List[str]:
        """
        从交易对列表中提取基础资产名
        ['BTCUSDT', 'ETHUSDT'] -> ['BTC', 'ETH']
        """
        return [p.replace('USDT', '') for p in pairs if p.endswith('USDT')]
    
    def fetch_klines(
        self,
        symbol: str,
        interval: str = '1d',
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        获取 K 线数据（自动选择现货或合约 API）
        
        Args:
            symbol: 交易对，如 'BTCUSDT'
            interval: 时间粒度 '1m','5m','15m','1h','4h','1d' 等
            start_time: 开始时间（UTC）
            end_time: 结束时间（UTC）
            limit: 单次最多返回条数（最大 1000）
        
        Returns:
            List of OHLCV dicts
        """
        # 如果 symbol 不在任何缓存中，先预检测其可用市场
        if symbol not in self._futures_symbols and symbol not in self._spot_symbols:
            # 用快速检测确定市场类型
            market_type = self._check_symbol_availability(symbol)
            if market_type == 'none':
                logger.warning(f"[Binance] {symbol} not available on Spot or Futures")
                return []
        
        # 确定使用哪个 API
        if symbol in self._futures_symbols:
            base_url = self.futures_url
            market = "Futures"
        else:
            base_url = self.spot_url
            market = "Spot"
        
        try:
            url = f"{base_url}/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            if start_time:
                params['startTime'] = int(start_time.timestamp() * 1000)
            if end_time:
                params['endTime'] = int(end_time.timestamp() * 1000)
            
            time.sleep(self.rate_limit_delay)
            response = self.session.get(url, params=params, timeout=30)
            
            response.raise_for_status()
            data = response.json()
            
            # 币安返回格式: [open_time, open, high, low, close, volume, ...]
            result = []
            for kline in data:
                dt = datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc)
                result.append({
                    'timestamp': kline[0],
                    'datetime': dt.isoformat(),
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5]),
                })
            
            if result:
                logger.info(f"[Binance] Fetched {len(result)} {interval} klines for {symbol} ({market})")
            
            return result
            
        except Exception as e:
            logger.error(f"[Binance] Failed to fetch {symbol} {interval}: {e}")
            return []
    
    def fetch_historical_klines_batch(
        self,
        symbol: str,
        interval: str,
        days: int = 90
    ) -> List[Dict]:
        """
        批量获取历史 K 线（从当前时间往前抓取，最多 days 天）
        币安单次最多 1000 条，需要分段拉取
        """
        all_klines = []
        now = datetime.now(timezone.utc)
        earliest_time = now - timedelta(days=days)
        
        # 计算时间跨度
        interval_map = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1),
        }
        
        delta = interval_map.get(interval, timedelta(days=1))
        max_per_request = 1000
        chunk_duration = delta * max_per_request
        
        # 从当前时间往前抓取
        current_end = now
        
        while current_end > earliest_time:
            current_start = max(current_end - chunk_duration, earliest_time)
            
            klines = self.fetch_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=current_end,
                limit=max_per_request
            )
            
            if klines:
                # 插入到列表前面（因为是从后往前抓的）
                all_klines = klines + all_klines
                # 移动到更早的时间段
                first_time = datetime.fromisoformat(klines[0]['datetime'])
                current_end = first_time - delta
            else:
                # 没有数据，尝试更早的时间段
                current_end = current_start - delta
            
            # 如果已经抓到足够早的数据，停止
            if current_end <= earliest_time:
                break
        
        logger.info(f"[Binance] Fetched {len(all_klines)} {interval} klines for {symbol}")
        return all_klines
    
    def fetch_multiple_symbols(
        self,
        symbols: List[str],
        interval: str = '1d',
        days: int = 90,
        max_workers: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        并发获取多个交易对的 K 线数据
        
        Returns:
            {
                'BTCUSDT': [kline1, kline2, ...],
                'ETHUSDT': [...],
                ...
            }
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(
                    self.fetch_historical_klines_batch,
                    symbol,
                    interval,
                    days
                ): symbol
                for symbol in symbols
            }
            
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    klines = future.result()
                    if klines:
                        results[symbol] = klines
                except Exception as e:
                    logger.error(f"[Binance] Error fetching {symbol}: {e}")
        
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = BinancePriceFetcher()
    
    # 测试单个交易对
    print("Testing single symbol fetch...")
    klines = fetcher.fetch_historical_klines_batch('BTCUSDT', '1d', days=7)
    print(f"Fetched {len(klines)} daily klines for BTCUSDT")
    if klines:
        print(f"Latest: {klines[-1]}")
    
    # 测试批量
    print("\nTesting batch fetch...")
    results = fetcher.fetch_multiple_symbols(
        ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
        interval='1d',
        days=7,
        max_workers=3
    )
    for symbol, klines in results.items():
        print(f"{symbol}: {len(klines)} klines")
