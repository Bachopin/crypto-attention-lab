#!/usr/bin/env python3
"""
多币种价格数据批量获取
支持主流加密货币的历史价格数据抓取
"""
import sys
import ccxt
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import RAW_DATA_DIR
from src.data.db_storage import get_db, USE_DATABASE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 主流币种与交易对映射
SYMBOL_PAIRS = {
    "BTC": "BTC/USDT",
    "ETH": "ETH/USDT",
    "ZEC": "ZEC/USDT",
    "XMR": "XMR/USDT",
    "SOL": "SOL/USDT",
    "ADA": "ADA/USDT",
    "DOGE": "DOGE/USDT",
    "XRP": "XRP/USDT",
}

# 时间周期列表
TIMEFRAMES = ["1d", "4h", "1h", "15m"]


def fetch_price_data(
    exchange,
    symbol: str,
    timeframe: str,
    days: int = 500,
    limit: int = 1000
) -> pd.DataFrame:
    """
    从交易所抓取价格数据
    
    Args:
        exchange: ccxt 交易所实例
        symbol: 交易对，如 'BTC/USDT'
        timeframe: K线周期
        days: 历史天数
        limit: 单次请求数量
    """
    logger.info(f"Fetching {symbol} {timeframe} (last {days} days)...")
    
    # 计算时间范围
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    
    all_ohlcv = []
    current_since = since
    
    try:
        while True:
            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe,
                since=current_since,
                limit=limit
            )
            
            if not ohlcv:
                break
            
            all_ohlcv.extend(ohlcv)
            
            # 更新时间指针
            current_since = ohlcv[-1][0] + 1
            
            # 检查是否到达当前时间
            if current_since >= exchange.milliseconds():
                break
            
            # 速率限制
            time.sleep(exchange.rateLimit / 1000)
            
            # 防止无限循环
            if len(all_ohlcv) > days * 500:  # 合理上限
                logger.warning(f"Reached data limit for {symbol} {timeframe}")
                break
        
        if not all_ohlcv:
            logger.warning(f"No data for {symbol} {timeframe}")
            return pd.DataFrame()
        
        # 转换为 DataFrame
        df = pd.DataFrame(
            all_ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        
        # 去重
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        
        logger.info(f"Fetched {len(df)} candles for {symbol} {timeframe}")
        return df
        
    except Exception as e:
        logger.error(f"Error fetching {symbol} {timeframe}: {e}")
        return pd.DataFrame()


def save_to_database(symbol_base: str, timeframe: str, df: pd.DataFrame):
    """保存到数据库"""
    if not USE_DATABASE or df.empty:
        return
    
    try:
        db = get_db()
        records = []
        
        for _, row in df.iterrows():
            records.append({
                "timestamp": int(row["timestamp"]),
                "datetime": row["datetime"].isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        
        db.save_prices(symbol_base, timeframe, records)
        logger.info(f"Saved {len(records)} records to database for {symbol_base} {timeframe}")
        
    except Exception as e:
        logger.error(f"Failed to save to database: {e}")


def save_to_csv(symbol_pair: str, timeframe: str, df: pd.DataFrame):
    """CSV 备份"""
    if df.empty:
        return
    
    # 标准化文件名
    symbol_clean = symbol_pair.replace("/", "")
    filename = f"price_{symbol_clean}_{timeframe}.csv"
    filepath = RAW_DATA_DIR / filename
    
    # 选择列
    df_save = df[["timestamp", "datetime", "open", "high", "low", "close", "volume"]]
    df_save.to_csv(filepath, index=False)
    
    logger.info(f"Saved to {filepath}")


def main():
    """批量抓取主流币种价格"""
    logger.info("Starting multi-symbol price fetch...")
    
    # 初始化交易所（Binance）
    try:
        exchange = ccxt.binance({
            "enableRateLimit": True,
            "timeout": 30000,
        })
        logger.info(f"Initialized exchange: {exchange.name}")
    except Exception as e:
        logger.error(f"Failed to initialize exchange: {e}")
        return
    
    # 批量抓取
    for symbol_base, symbol_pair in SYMBOL_PAIRS.items():
        logger.info(f"\n=== Processing {symbol_base} ({symbol_pair}) ===")
        
        for timeframe in TIMEFRAMES:
            # 根据时间周期调整历史天数
            if timeframe in ["1d"]:
                days = 500  # 约 1.4 年
            elif timeframe in ["4h", "1h"]:
                days = 365  # 1 年
            elif timeframe == "15m":
                days = 90   # 3 个月
            else:
                days = 180
            
            df = fetch_price_data(exchange, symbol_pair, timeframe, days=days)
            
            if not df.empty:
                # 仅保存到数据库（不生成CSV）
                save_to_database(symbol_base, timeframe, df)
            
            # 速率限制
            time.sleep(1)
    
    logger.info("\n=== Price fetch completed ===")
    
    # 统计
    if USE_DATABASE:
        try:
            db = get_db()
            symbols = db.get_all_symbols()
            logger.info(f"Total symbols in database: {len(symbols)}")
            logger.info(f"Symbols: {', '.join(symbols)}")
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")


if __name__ == "__main__":
    main()
