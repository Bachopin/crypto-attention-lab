#!/usr/bin/env python3
"""获取ZEC历史价格数据(1d/4h/1h/15m) - 存储到数据库"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import pandas as pd
import logging

from src.data.db_storage import save_price_data
from src.config.settings import TRACKED_SYMBOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://min-api.cryptocompare.com/data/v2"


def fetch_daily_data(symbol: str, days: int = 90) -> pd.DataFrame:
    """从 CryptoCompare 获取日线数据 (不生成)"""
    url = f"{BASE_URL}/histoday"
    params = {"fsym": symbol, "tsym": "USD", "limit": days}
    
    logger.info(f"Fetching {days} days of {symbol} data...")
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()['Data']['Data']
    
    df = pd.DataFrame(data)
    df['timestamp'] = df['time'] * 1000
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.rename(columns={'volumefrom': 'volume'})
    df = df[['datetime', 'timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    logger.info(f"Fetched {len(df)} daily candles for {symbol}, latest: ${df['close'].iloc[-1]:.2f}")
    return df

def fetch_histohour(symbol: str, hours: int = 24 * 60, aggregate: int = 1) -> pd.DataFrame:
    """从 CryptoCompare 获取小时数据; aggregate 可为 1(1h) 或 4(4h)。"""
    url = f"{BASE_URL}/histohour"
    limit = min(hours // aggregate, 2000)  # API 限制
    params = {"fsym": symbol, "tsym": "USD", "limit": limit, "aggregate": aggregate}
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()["Data"]["Data"]
    df = pd.DataFrame(data)
    df = df.rename(columns={"time": "timestamp", "volumefrom": "volume"})
    df["timestamp"] = df["timestamp"] * 1000
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df[["datetime", "timestamp", "open", "high", "low", "close", "volume"]]
    logger.info(f"Fetched {len(df)} histohour candles for {symbol} (agg={aggregate})")
    return df


def fetch_histominute(symbol: str, minutes: int = 24 * 60, aggregate: int = 15) -> pd.DataFrame:
    """从 CryptoCompare 获取分钟数据; aggregate=15 获取 15m。"""
    url = f"{BASE_URL}/histominute"
    limit = min(minutes // aggregate, 2000)
    params = {"fsym": symbol, "tsym": "USD", "limit": limit, "aggregate": aggregate}
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()["Data"]["Data"]
    df = pd.DataFrame(data)
    df = df.rename(columns={"time": "timestamp", "volumefrom": "volume"})
    df["timestamp"] = df["timestamp"] * 1000
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df[["datetime", "timestamp", "open", "high", "low", "close", "volume"]]
    logger.info(f"Fetched {len(df)} histominute candles for {symbol} (agg={aggregate})")
    return df

def save_data(symbol_pair: str, df, timeframe):
    """保存数据到数据库"""
    # 提取基础资产符号 (如 "ZEC/USDT" -> "ZEC")
    base_symbol = symbol_pair.split('/')[0]
    records = df.to_dict('records')
    # 使用基础资产符号保存，确保数据库中 Symbol 表统一为资产名
    count = save_price_data(base_symbol, timeframe, records)
    logger.info(f"Saved {count} {timeframe} price records for {base_symbol} (from {symbol_pair}) to database")

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Fetching price data for all tracked symbols...")
    
    for symbol_pair in TRACKED_SYMBOLS:
        # symbol_pair 格式如 "ZEC/USDT"
        base_symbol = symbol_pair.split('/')[0]
        logger.info(f"Processing {symbol_pair}...")
        
        try:
            # 日线: 90 天
            daily_df = fetch_daily_data(base_symbol, 90)
            save_data(symbol_pair, daily_df, "1d")

            # 小时: 60 天的数据 (60*24 小时)
            one_hour_df = fetch_histohour(base_symbol, hours=60*24, aggregate=1)
            save_data(symbol_pair, one_hour_df, "1h")

            # 四小时: 90 天的数据 (90*6 个4小时bar)
            four_hour_df = fetch_histohour(base_symbol, hours=90*24, aggregate=4)
            save_data(symbol_pair, four_hour_df, "4h")

            # 15分钟: 最近 30 天 (30*24*60 / 15)
            fifteen_min_df = fetch_histominute(base_symbol, minutes=30*24*60, aggregate=15)
            save_data(symbol_pair, fifteen_min_df, "15m")
            
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol_pair}: {e}")

    logger.info("\n" + "="*60)
    logger.info("✓ All price data saved to database successfully!")
    logger.info("Price data update completed!")
