#!/usr/bin/env python3
"""
重新获取历史价格数据（扩展到500天）
用于将现有币种的历史数据从90天扩展到500天
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from src.data.realtime_price_updater import get_realtime_updater
from src.database.models import Symbol, get_session

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_enabled_symbols():
    """获取所有启用的币种"""
    session = get_session()
    try:
        symbols = session.query(Symbol).filter(
            Symbol.is_active == True
        ).all()
        return [s.symbol for s in symbols]
    finally:
        session.close()


async def refetch_historical_data(symbols=None):
    """
    重新获取历史数据
    
    Args:
        symbols: 币种列表，None 表示所有启用的币种
    """
    if symbols is None:
        symbols = get_enabled_symbols()
    
    if not symbols:
        logger.warning("No symbols found to update")
        return
    
    logger.info(f"Will refetch historical data for {len(symbols)} symbols: {symbols}")
    logger.info("This will fetch ~500 days of historical data for each symbol")
    
    # 确认
    response = input("\nProceed? (y/n): ")
    if response.lower() != 'y':
        logger.info("Cancelled by user")
        return
    
    updater = get_realtime_updater()
    
    for symbol in symbols:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {symbol}")
        logger.info(f"{'='*60}")
        
        try:
            # 传递 None 作为 last_update，触发完整历史数据获取（500天）
            await updater.update_single_symbol(symbol, last_update=None)
            logger.info(f"✅ {symbol} completed")
        except Exception as e:
            logger.error(f"❌ {symbol} failed: {e}")
    
    logger.info(f"\n{'='*60}")
    logger.info("Historical data refetch completed!")
    logger.info(f"{'='*60}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Refetch historical price data (500 days)')
    parser.add_argument(
        '--symbols',
        nargs='+',
        help='Specific symbols to update (e.g., BTC ETH). If not provided, all enabled symbols will be updated.'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Update all enabled symbols without confirmation'
    )
    
    args = parser.parse_args()
    
    symbols = args.symbols
    
    # 显示当前配置
    logger.info("="*60)
    logger.info("Historical Data Refetch Tool")
    logger.info("="*60)
    logger.info(f"Configuration:")
    logger.info(f"  - Data range: 500 days (~1.4 years)")
    logger.info(f"  - Timeframes: 1d, 4h, 1h, 15m")
    
    if symbols:
        logger.info(f"  - Target symbols: {', '.join(symbols)}")
    else:
        logger.info(f"  - Target: All enabled symbols")
    
    logger.info("="*60)
    
    # 运行
    asyncio.run(refetch_historical_data(symbols))


if __name__ == '__main__':
    main()
