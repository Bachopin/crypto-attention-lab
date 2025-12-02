"""
时间戳处理工具模块

解决项目中时间戳不一致的根本问题：
1. 所有 datetime 统一使用 UTC timezone-aware
2. 日级数据对齐使用 normalize() 而非 .dt.date
3. 数据库读取后强制转换为 UTC

使用指南：
- to_utc(): 将任意 datetime 转为 UTC timezone-aware
- normalize_to_date(): 截取到 UTC 日期的 00:00:00（用于日级数据对齐）
- ensure_utc_column(): 确保 DataFrame 的 datetime 列是 UTC
"""

from datetime import datetime, timezone, date
from typing import Optional, Union
import pandas as pd
import logging

logger = logging.getLogger(__name__)

DatetimeLike = Union[datetime, pd.Timestamp, str, int, float, date, None]


def to_utc(dt: DatetimeLike) -> Optional[pd.Timestamp]:
    """
    将任意 datetime-like 值转换为 UTC timezone-aware Timestamp
    
    支持的输入格式：
    - datetime (naive 或 aware)
    - pd.Timestamp
    - ISO 格式字符串
    - Unix 毫秒时间戳 (int/float)
    - date 对象
    - None (返回 None)
    
    Examples:
        >>> to_utc('2025-12-01')
        Timestamp('2025-12-01 00:00:00+0000', tz='UTC')
        
        >>> to_utc(1733011200000)  # Unix毫秒
        Timestamp('2025-12-01 00:00:00+0000', tz='UTC')
        
        >>> to_utc(datetime(2025, 12, 1, 8, 0, 0))  # naive
        Timestamp('2025-12-01 08:00:00+0000', tz='UTC')
    """
    if dt is None:
        return None
    
    try:
        # Unix 毫秒时间戳
        if isinstance(dt, (int, float)):
            # 如果是毫秒级（>1e12），转换为秒
            if dt > 1e12:
                dt = dt / 1000
            # 直接创建 UTC 时间戳
            return pd.Timestamp(dt, unit='s', tz='UTC')
        
        # date 对象（无时间部分）
        if isinstance(dt, date) and not isinstance(dt, datetime):
            return pd.Timestamp(dt).tz_localize('UTC')
        
        # 转为 Timestamp
        ts = pd.Timestamp(dt)
        
        if ts.tz is None:
            # naive datetime → 假设是 UTC
            return ts.tz_localize('UTC')
        else:
            # 带时区 → 转换为 UTC
            return ts.tz_convert('UTC')
    
    except Exception as e:
        logger.warning(f"Failed to convert {dt} to UTC: {e}")
        return None


def normalize_to_date(dt: DatetimeLike) -> Optional[pd.Timestamp]:
    """
    截取到 UTC 日期的 00:00:00（保留时区信息）
    
    用于日级数据对齐，替代 .dt.date（会丢失时区）
    
    Examples:
        >>> normalize_to_date('2025-12-01 16:00:00+00:00')
        Timestamp('2025-12-01 00:00:00+0000', tz='UTC')
        
        >>> normalize_to_date('2025-12-02 02:00:00+08:00')  # Asia/Shanghai
        Timestamp('2025-12-01 00:00:00+0000', tz='UTC')  # 转为 UTC 后是前一天
    """
    utc_ts = to_utc(dt)
    if utc_ts is None:
        return None
    return utc_ts.normalize()


def ensure_utc_column(df: pd.DataFrame, column: str = 'datetime') -> pd.DataFrame:
    """
    确保 DataFrame 的指定 datetime 列是 UTC timezone-aware
    
    这是数据库读取后的标准处理步骤：
    - PostgreSQL TIMESTAMPTZ 可能返回服务器本地时区
    - 需要统一转换为 UTC
    
    Args:
        df: 输入 DataFrame
        column: 日期时间列名，默认 'datetime'
    
    Returns:
        修改后的 DataFrame（原地修改）
    
    Examples:
        >>> df = pd.DataFrame({'datetime': ['2025-12-01 08:00:00+08:00']})
        >>> ensure_utc_column(df)
        >>> df['datetime'][0]
        Timestamp('2025-12-01 00:00:00+0000', tz='UTC')
    """
    if df.empty or column not in df.columns:
        return df
    
    # 先解析为 datetime
    df[column] = pd.to_datetime(df[column])
    
    # 检查是否有时区信息
    if df[column].dt.tz is None:
        # naive → 假设是 UTC
        df[column] = df[column].dt.tz_localize('UTC')
    else:
        # 有时区 → 转换为 UTC
        df[column] = df[column].dt.tz_convert('UTC')
    
    return df


def add_date_column(df: pd.DataFrame, 
                    datetime_col: str = 'datetime', 
                    date_col: str = '_date') -> pd.DataFrame:
    """
    添加日期列（用于日级数据对齐）
    
    使用 normalize() 而非 .dt.date，保留时区信息
    
    Args:
        df: 输入 DataFrame
        datetime_col: 源日期时间列名
        date_col: 目标日期列名
    
    Returns:
        添加了日期列的 DataFrame（原地修改）
    """
    if df.empty or datetime_col not in df.columns:
        return df
    
    # 确保源列是 UTC
    ensure_utc_column(df, datetime_col)
    
    # 使用 normalize() 截取到日期
    df[date_col] = df[datetime_col].dt.normalize()
    
    return df


def utc_now() -> pd.Timestamp:
    """
    获取当前 UTC 时间（timezone-aware）
    
    Returns:
        当前 UTC 时间的 Timestamp
    """
    return pd.Timestamp.now(tz='UTC')


def to_iso_utc(dt: DatetimeLike) -> Optional[str]:
    """
    输出 ISO 8601 格式的 UTC 时间字符串
    
    格式: "2025-12-01T00:00:00Z"
    
    用于 API 响应，确保前端能正确解析
    """
    utc_ts = to_utc(dt)
    if utc_ts is None:
        return None
    return utc_ts.strftime('%Y-%m-%dT%H:%M:%SZ')


def align_daily_dataframes(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    datetime_col: str = 'datetime',
    how: str = 'inner'
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    对齐两个日级数据的 DataFrame
    
    解决价格数据（16:00:00）和注意力数据（00:00:00）时间戳不一致的问题
    
    Args:
        df1, df2: 要对齐的两个 DataFrame
        datetime_col: 日期时间列名
        how: 对齐方式 ('inner', 'outer', 'left', 'right')
    
    Returns:
        对齐后的两个 DataFrame（基于日期对齐）
    """
    # 添加日期列
    add_date_column(df1, datetime_col, '_align_date')
    add_date_column(df2, datetime_col, '_align_date')
    
    # 找到共同日期
    if how == 'inner':
        common_dates = set(df1['_align_date']) & set(df2['_align_date'])
    elif how == 'outer':
        common_dates = set(df1['_align_date']) | set(df2['_align_date'])
    elif how == 'left':
        common_dates = set(df1['_align_date'])
    elif how == 'right':
        common_dates = set(df2['_align_date'])
    else:
        raise ValueError(f"Unknown how: {how}")
    
    # 过滤
    df1_aligned = df1[df1['_align_date'].isin(common_dates)].copy()
    df2_aligned = df2[df2['_align_date'].isin(common_dates)].copy()
    
    # 清理临时列
    df1_aligned.drop(columns=['_align_date'], inplace=True, errors='ignore')
    df2_aligned.drop(columns=['_align_date'], inplace=True, errors='ignore')
    
    return df1_aligned, df2_aligned
