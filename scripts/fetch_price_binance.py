#!/usr/bin/env python3
"""
币安价格数据批量抓取脚本
支持多时间粒度、增量更新、并发控制
"""
import logging
import argparse
from datetime import datetime, timezone
from src.data.price_fetcher_binance import BinancePriceFetcher
from src.data.db_storage import get_db, save_price_data
from src.config.settings import TRACKED_SYMBOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_and_save_binance_prices(
    symbols: list = None,
    timeframes: list = None,
    days: int = 90,
    batch_size: int = 100,
    max_workers: int = 5
):
    """
    批量获取并保存币安价格数据
    
    Args:
        symbols: 要抓取的交易对列表，如 ['BTCUSDT', 'ETHUSDT']，None 则抓取所有
        timeframes: 时间粒度列表，如 ['1d', '4h', '1h', '15m']
        days: 历史数据天数
        batch_size: 每批处理的交易对数量
        max_workers: 并发线程数
    """
    fetcher = BinancePriceFetcher()
    db = get_db()
    
    # 默认时间粒度
    if timeframes is None:
        timeframes = ['1d', '4h', '1h', '15m']
    
    # 获取要抓取的交易对列表
    if symbols is None:
        all_pairs = fetcher.get_all_usdt_pairs()
        logger.info(f"Auto-detected {len(all_pairs)} USDT pairs from Binance")
        symbols = all_pairs
    
    # 分批处理
    total_symbols = len(symbols)
    for i in range(0, total_symbols, batch_size):
        batch = symbols[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_symbols + batch_size - 1) // batch_size
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} symbols)...")
        
        for timeframe in timeframes:
            logger.info(f"  Fetching {timeframe} data...")
            
            # 币安 API 的时间粒度映射
            interval_map = {
                '1d': '1d',
                '4h': '4h',
                '1h': '1h',
                '15m': '15m',
            }
            interval = interval_map.get(timeframe, '1d')
            
            # 并发获取本批次数据
            results = fetcher.fetch_multiple_symbols(
                batch,
                interval=interval,
                days=days,
                max_workers=max_workers
            )
            
            # 保存到数据库
            for symbol_pair, klines in results.items():
                if not klines:
                    continue
                
                # 提取基础资产名（BTCUSDT -> BTC）
                base_symbol = symbol_pair.replace('USDT', '')
                
                try:
                    save_price_data(base_symbol, timeframe, klines)
                    logger.info(f"    Saved {len(klines)} {timeframe} records for {base_symbol}")
                except Exception as e:
                    logger.error(f"    Failed to save {base_symbol} {timeframe}: {e}")
    
    logger.info("=" * 60)
    logger.info("✅ Binance price data fetch completed!")


def main():
    parser = argparse.ArgumentParser(description='Fetch Binance price data')
    parser.add_argument('--symbols', type=str, help='Comma-separated symbol list (e.g., BTC,ETH,SOL)')
    parser.add_argument('--timeframes', type=str, default='1d,4h,1h,15m', help='Comma-separated timeframes')
    parser.add_argument('--days', type=int, default=90, help='Historical data days')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing')
    parser.add_argument('--max-workers', type=int, default=5, help='Max concurrent workers')
    parser.add_argument('--tracked-only', action='store_true', help='Only fetch tracked symbols from config')
    
    args = parser.parse_args()
    
    # 解析参数
    if args.tracked_only:
        from src.config.settings import TRACKED_SYMBOLS
        symbols = [s.replace('/', '') for s in TRACKED_SYMBOLS]  # ZEC/USDT -> ZECUSDT
    elif args.symbols:
        symbols = [f"{s.strip().upper()}USDT" for s in args.symbols.split(',')]
    else:
        symbols = None  # 获取所有
    
    timeframes = [tf.strip() for tf in args.timeframes.split(',')]
    
    logger.info("=" * 60)
    logger.info("Binance Price Data Fetcher")
    logger.info("=" * 60)
    logger.info(f"Symbols: {symbols or 'ALL (auto-detect)'}")
    logger.info(f"Timeframes: {timeframes}")
    logger.info(f"Historical days: {args.days}")
    logger.info(f"Batch size: {args.batch_size}")
    logger.info(f"Max workers: {args.max_workers}")
    logger.info("=" * 60)
    
    fetch_and_save_binance_prices(
        symbols=symbols,
        timeframes=timeframes,
        days=args.days,
        batch_size=args.batch_size,
        max_workers=args.max_workers
    )


if __name__ == "__main__":
    main()
