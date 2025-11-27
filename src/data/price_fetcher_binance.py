#!/usr/bin/env python3
"""
Binance Price Fetcher - 无需 API Key 的公共行情接口
支持批量获取 USDT 计价交易对的 K 线数据
"""
import requests
import pandas as pd
import time
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

BASE_URL = "https://api.binance.com/api/v3"
RATE_LIMIT_DELAY = 0.1  # 每个请求间隔 100ms，避免触发限流


class BinancePriceFetcher:
    """币安价格数据获取器"""
    
    def __init__(self, rate_limit_delay: float = RATE_LIMIT_DELAY):
        self.base_url = BASE_URL
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})
    
    def get_all_usdt_pairs(self) -> List[str]:
        """
        获取所有 USDT 计价的活跃交易对
        Returns: ['BTCUSDT', 'ETHUSDT', ...]
        """
        try:
            url = f"{self.base_url}/exchangeInfo"
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
        获取 K 线数据
        
        Args:
            symbol: 交易对，如 'BTCUSDT'
            interval: 时间粒度 '1m','5m','15m','1h','4h','1d' 等
            start_time: 开始时间（UTC）
            end_time: 结束时间（UTC）
            limit: 单次最多返回条数（最大 1000）
        
        Returns:
            List of OHLCV dicts
        """
        try:
            url = f"{self.base_url}/klines"
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
        批量获取历史 K 线（自动分段）
        币安单次最多 1000 条，需要分段拉取
        """
        all_klines = []
        end_time = datetime.now(timezone.utc)
        
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
        
        start_time = end_time - timedelta(days=days)
        current_start = start_time
        
        while current_start < end_time:
            current_end = min(current_start + chunk_duration, end_time)
            
            klines = self.fetch_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=current_end,
                limit=max_per_request
            )
            
            if not klines:
                break
            
            all_klines.extend(klines)
            
            # 移动到下一段
            last_time = datetime.fromisoformat(klines[-1]['datetime'])
            current_start = last_time + delta
            
            if len(klines) < max_per_request:
                # 已经拉完了
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
