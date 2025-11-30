"""
数据存储和加载工具函数
提供统一的 CSV 文件读取和时间范围过滤功能
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import logging

from src.config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR

logger = logging.getLogger(__name__)


def load_price_data(
    symbol: str,
    timeframe: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
) -> Tuple[pd.DataFrame, bool]:
    """
    加载价格数据
    
    Args:
        symbol: 标的符号，如 "ZECUSDT"
        timeframe: 时间周期，如 "1d", "4h", "1h", "15m"
        start: 开始时间
        end: 结束时间
        
    Returns:
        (DataFrame, is_fallback): 价格数据和是否是 fallback 数据
    """
    # 尝试主文件
    price_file = RAW_DATA_DIR / f"price_{symbol}_{timeframe}.csv"
    fallback_file = RAW_DATA_DIR / f"price_{symbol}_{timeframe}_fallback.csv"
    
    is_fallback = False
    
    if price_file.exists():
        df = pd.read_csv(price_file)
    elif fallback_file.exists():
        df = pd.read_csv(fallback_file)
        is_fallback = True
    else:
        logger.warning(f"Price data not found for {symbol} {timeframe}")
        return pd.DataFrame(), True
    
    # 转换时间列
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True, errors='coerce')
    
    # 时间范围过滤 - 确保类型一致
    if start is not None:
        start_ts = pd.Timestamp(start, tz='UTC') if not hasattr(start, 'tz') else start
        df = df[df['datetime'] >= start_ts]
    if end is not None:
        end_ts = pd.Timestamp(end, tz='UTC') if not hasattr(end, 'tz') else end
        df = df[df['datetime'] <= end_ts]
    
    return df, is_fallback


def load_attention_data(
    symbol: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
) -> pd.DataFrame:
    """
    加载处理后的注意力特征数据
    
    Args:
        symbol: 标的符号，如 "ZEC"
        start: 开始时间
        end: 结束时间
        
    Returns:
        DataFrame: 包含 datetime, attention_score, news_count 等字段
    """
    # 目前只支持 ZEC，将来可扩展
    symbol_lower = symbol.lower()
    attention_file = PROCESSED_DATA_DIR / f"attention_features_{symbol_lower}.csv"
    
    if not attention_file.exists():
        logger.warning(f"Attention features not found for {symbol}")
        return pd.DataFrame()
    
    df = pd.read_csv(attention_file)
    
    # 转换时间列为 datetime
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True, errors='coerce')
    
    # 时间范围过滤 - 确保类型一致
    if start is not None:
        start_ts = pd.Timestamp(start, tz='UTC') if not hasattr(start, 'tz') else start
        df = df[df['datetime'] >= start_ts]
    if end is not None:
        end_ts = pd.Timestamp(end, tz='UTC') if not hasattr(end, 'tz') else end
        df = df[df['datetime'] <= end_ts]
    
    return df


def load_news_data(
    symbol: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
) -> pd.DataFrame:
    """
    加载原始新闻数据
    
    Args:
        symbol: 标的符号，如 "ZEC"
        start: 开始时间
        end: 结束时间
        
    Returns:
        DataFrame: 包含 datetime, source, title, url 等字段
    """
    symbol_lower = symbol.lower()
    
    # 优先使用真实新闻，否则 fallback 到 mock
    news_file = RAW_DATA_DIR / f"attention_{symbol_lower}_news.csv"
    mock_file = RAW_DATA_DIR / f"attention_{symbol_lower}_mock.csv"
    
    if news_file.exists():
        df = pd.read_csv(news_file)
    elif mock_file.exists():
        df = pd.read_csv(mock_file)
    else:
        logger.warning(f"News data not found for {symbol}")
        return pd.DataFrame()
    
    # 转换时间列
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True, errors='coerce')
    
    # 时间范围过滤 - 确保类型一致
    if start is not None:
        start_ts = pd.Timestamp(start, tz='UTC') if not hasattr(start, 'tz') else start
        df = df[df['datetime'] >= start_ts]
    if end is not None:
        end_ts = pd.Timestamp(end, tz='UTC') if not hasattr(end, 'tz') else end
        df = df[df['datetime'] <= end_ts]
    
    return df


def ensure_price_data_exists(symbol: str, timeframe: str) -> bool:
    """
    确保价格数据文件存在，如果不存在则尝试获取
    
    Args:
        symbol: 标的符号，如 "ZECUSDT"
        timeframe: 时间周期
        
    Returns:
        bool: 数据是否可用
    """
    price_file = RAW_DATA_DIR / f"price_{symbol}_{timeframe}.csv"
    fallback_file = RAW_DATA_DIR / f"price_{symbol}_{timeframe}_fallback.csv"
    
    if price_file.exists() or fallback_file.exists():
        return True
    
    # 数据不存在 - 应该由后台服务或手动脚本获取
    logger.warning(f"Price data not found for {symbol} {timeframe}. "
                   f"Please run realtime_price_updater or fetch_multi_symbol_prices.py")
    return False


def ensure_attention_data_exists(symbol: str) -> bool:
    """
    确保注意力数据存在，如果不存在则尝试获取并处理
    
    数据库优先模式：检查数据库中是否有对应 symbol 的 attention features。
    如果没有，则触发 attention features 的计算。
    
    注意：新闻数据是全局获取的，不限于特定代币。
    Attention 计算时会按代币符号和时间过滤相关新闻。
    
    Args:
        symbol: 标的符号，如 "ZEC"
        
    Returns:
        bool: 数据是否可用
    """
    from src.data.db_storage import USE_DATABASE, get_db
    
    if USE_DATABASE:
        try:
            db = get_db()
            df = db.get_attention_features(symbol)
            if not df.empty:
                return True
            
            # 数据库中没有数据，尝试计算
            logger.info(f"No attention data in DB for {symbol}, generating...")
            from src.services.attention_service import AttentionService
            result = AttentionService.update_attention_features(symbol=symbol)
            return result is not None and not result.empty
        except Exception as e:
            logger.error(f"Failed to check/generate attention data from DB: {e}")
            return False
    
    # CSV fallback 模式
    symbol_lower = symbol.lower()
    attention_file = PROCESSED_DATA_DIR / f"attention_features_{symbol_lower}.csv"
    
    if attention_file.exists():
        return True
    
    # 尝试计算 attention features
    try:
        from src.services.attention_service import AttentionService
        
        logger.info(f"Processing attention features for {symbol}")
        result = AttentionService.update_attention_features(symbol=symbol)
        
        return result is not None and not result.empty
    except Exception as e:
        logger.error(f"Failed to process attention data: {e}")
        return False
