#!/usr/bin/env python3
"""获取ZEC历史价格数据(1d/4h/1h/15m) - 全部来自远程数据源"""
import requests
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://min-api.cryptocompare.com/data/v2"


def fetch_daily_data(days: int = 90) -> pd.DataFrame:
    """从 CryptoCompare 获取日线数据 (不生成)"""
    url = f"{BASE_URL}/histoday"
    params = {"fsym": "ZEC", "tsym": "USD", "limit": days}
    
    logger.info(f"Fetching {days} days of ZEC data...")
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()['Data']['Data']
    
    df = pd.DataFrame(data)
    df['timestamp'] = df['time'] * 1000
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.rename(columns={'volumefrom': 'volume'})
    df = df[['datetime', 'timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    logger.info(f"Fetched {len(df)} daily candles, latest: ${df['close'].iloc[-1]:.2f}")
    return df

def fetch_histohour(hours: int = 24 * 60, aggregate: int = 1) -> pd.DataFrame:
    """从 CryptoCompare 获取小时数据; aggregate 可为 1(1h) 或 4(4h)。"""
    url = f"{BASE_URL}/histohour"
    limit = min(hours // aggregate, 2000)  # API 限制
    params = {"fsym": "ZEC", "tsym": "USD", "limit": limit, "aggregate": aggregate}
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()["Data"]["Data"]
    df = pd.DataFrame(data)
    df = df.rename(columns={"time": "timestamp", "volumefrom": "volume"})
    df["timestamp"] = df["timestamp"] * 1000
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df[["datetime", "timestamp", "open", "high", "low", "close", "volume"]]
    logger.info(f"Fetched {len(df)} histohour candles (agg={aggregate})")
    return df


def fetch_histominute(minutes: int = 24 * 60, aggregate: int = 15) -> pd.DataFrame:
    """从 CryptoCompare 获取分钟数据; aggregate=15 获取 15m。"""
    url = f"{BASE_URL}/histominute"
    limit = min(minutes // aggregate, 2000)
    params = {"fsym": "ZEC", "tsym": "USD", "limit": limit, "aggregate": aggregate}
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()["Data"]["Data"]
    df = pd.DataFrame(data)
    df = df.rename(columns={"time": "timestamp", "volumefrom": "volume"})
    df["timestamp"] = df["timestamp"] * 1000
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df[["datetime", "timestamp", "open", "high", "low", "close", "volume"]]
    logger.info(f"Fetched {len(df)} histominute candles (agg={aggregate})")
    return df

def save_data(df, timeframe):
    """保存数据"""
    filepath = DATA_DIR / f"price_ZECUSDT_{timeframe}.csv"
    df.to_csv(filepath, index=False)
    logger.info(f"Saved {len(df)} rows to {filepath.name}")

if __name__ == "__main__":
    logger.info("="*60)
    # 日线: 90 天
    daily_df = fetch_daily_data(90)
    save_data(daily_df, "1d")

    # 小时: 60 天的数据 (60*24 小时)
    one_hour_df = fetch_histohour(hours=60*24, aggregate=1)
    save_data(one_hour_df, "1h")

    # 四小时: 90 天的数据 (90*6 个4小时bar)
    four_hour_df = fetch_histohour(hours=90*24, aggregate=4)
    save_data(four_hour_df, "4h")

    # 15分钟: 最近 30 天 (30*24*60 / 15)
    fifteen_min_df = fetch_histominute(minutes=30*24*60, aggregate=15)
    save_data(fifteen_min_df, "15m")

    # 5分钟: 最近 7 天
    five_min_df = fetch_histominute(minutes=7*24*60, aggregate=5)
    save_data(five_min_df, "5m")

    # 1分钟: 最近 2 天 (API限制2000条)
    one_min_df = fetch_histominute(minutes=2*24*60, aggregate=1)
    save_data(one_min_df, "1m")
    
    logger.info("\n" + "="*60)
    logger.info("Price data update completed!")
