import pandas as pd
from typing import Optional, List, Tuple
from datetime import datetime
import logging
from src.data.db_storage import load_price_data, load_attention_data, load_news_data, get_available_symbols

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Market Data Service: 负责获取、对齐和预处理多源数据。
    为 Research 和 Backtest 模块提供统一的数据视图。
    """

    @staticmethod
    def get_available_symbols() -> List[str]:
        """获取所有可用币种列表"""
        return get_available_symbols()

    @staticmethod
    def get_price_data(
        symbol: str,
        timeframe: str = '1d',
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        获取纯价格数据
        """
        # 规范化 Symbol
        symbol_upper = symbol.upper()
        if not symbol_upper.endswith("USDT") and not symbol_upper.endswith("USD"):
             price_symbol = f"{symbol_upper}USDT"
        else:
             price_symbol = symbol_upper

        df, _ = load_price_data(price_symbol, timeframe, start, end)
        if df is not None and not df.empty:
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
                df.set_index('datetime', inplace=True)
            df.reset_index(inplace=True)
        return df if df is not None else pd.DataFrame()

    @staticmethod
    def get_news_data(
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        获取新闻数据
        """
        df = load_news_data(symbol, start, end)
        if df is not None and not df.empty:
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        return df if df is not None else pd.DataFrame()

    @staticmethod
    def get_aligned_data(
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        timeframe: str = '1d',
        fill_method: str = 'ffill',
        attention_columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        获取已对齐的价格和注意力数据。
        
        Args:
            symbol: 代币符号 (e.g., "ZEC", "ZECUSDT")
            start: 开始时间 (UTC)
            end: 结束时间 (UTC)
            timeframe: 价格时间粒度 ('1d', '4h', etc.)
            fill_method: 缺失注意力数据的填充方式 ('ffill', 'bfill', None)

        Returns:
            DataFrame: 包含 price (open, close...) 和 attention (...) 列，
                       索引为 datetime (UTC)。
        """
        # 规范化 Symbol
        symbol_upper = symbol.upper()
        
        # 价格数据通常需要 USDT 后缀 (如果 DB 中是这样存储的)
        # 这里做一个简单的推断，如果不是以 USD/USDT 结尾，加上 USDT
        if not symbol_upper.endswith("USDT") and not symbol_upper.endswith("USD"):
             price_symbol = f"{symbol_upper}USDT"
        else:
             price_symbol = symbol_upper
        
        # 注意力数据通常没有后缀
        attention_symbol = symbol_upper.replace("USDT", "").replace("USD", "")

        # 1. 加载价格数据
        # load_price_data 返回 (DataFrame, is_fallback)
        price_df, _ = load_price_data(price_symbol, timeframe, start, end)
        
        if price_df is None or price_df.empty:
            logger.warning(f"No price data found for {price_symbol}")
            return pd.DataFrame()

        # 2. 加载注意力数据 (目前主要是日线)
        # 优先使用预存特征读取服务的列白名单能力
        try:
            from src.services.feature_service import FeatureService
            # timeframe 映射：价格的 '1d' 对应注意力的 'D'；'4h' 对应 '4H'
            tf_map = {'1d': 'D', '4h': '4H'}
            att_tf = tf_map.get(timeframe.lower(), 'D')
            attention_df = FeatureService.load_precomputed_features(
                attention_symbol,
                start=start,
                end=end,
                timeframe=att_tf,
                columns=attention_columns,
                fillna_zero=False,
                use_cache=True,
            )
        except Exception:
            # 回退到旧方法（拉取完整列）
            attention_df = load_attention_data(attention_symbol, start, end)
        
        # 3. 预处理与索引设置
        # 确保 price_df 有 datetime 索引
        if 'datetime' in price_df.columns:
            price_df['datetime'] = pd.to_datetime(price_df['datetime'], utc=True)
            price_df.set_index('datetime', inplace=True)
        elif not isinstance(price_df.index, pd.DatetimeIndex):
            # 如果既没有 datetime 列也不是 DatetimeIndex，可能数据有问题
            pass
            
        # 确保 attention_df 有 datetime 索引
        if not attention_df.empty:
            if 'datetime' in attention_df.columns:
                attention_df['datetime'] = pd.to_datetime(attention_df['datetime'], utc=True)
                attention_df.set_index('datetime', inplace=True)

        # 4. 数据对齐 (Left Join 以价格数据为基准)
        # 对于日线数据，价格和注意力的时间戳可能不完全对齐（时区差异导致小时不同）
        # 例如：价格 16:00 UTC，注意力 00:00 UTC（同一交易日）
        # 解决方案：对日线数据按 UTC 日期进行 merge，而非精确时间戳 join
        if timeframe.lower() == '1d' and not attention_df.empty:
            # 提取日期用于对齐
            price_df = price_df.reset_index()
            price_df['_merge_date'] = price_df['datetime'].dt.date
            
            attention_df = attention_df.reset_index()
            attention_df['_merge_date'] = attention_df['datetime'].dt.date
            # 重命名 attention 的 datetime 列避免冲突
            attention_df = attention_df.rename(columns={'datetime': 'datetime_att'})
            
            # 按日期 merge
            merged_df = price_df.merge(
                attention_df.drop(columns=['datetime_att'], errors='ignore'),
                on='_merge_date',
                how='left',
                suffixes=('', '_att')
            )
            # 删除辅助列并恢复索引
            merged_df = merged_df.drop(columns=['_merge_date'], errors='ignore')
            merged_df = merged_df.set_index('datetime')
        else:
            # 其他 timeframe 或无注意力数据时，使用原有逻辑
            merged_df = price_df.join(attention_df, how='left', rsuffix='_att')

        # 5. 缺失值处理
        # 注意力数据可能在周末或某些时段缺失，或者因为 timeframe 不一致(如4h价格 vs 1d注意力)
        if fill_method == 'ffill' and not attention_df.empty:
            # 仅对注意力列进行填充
            att_cols = attention_df.columns
            # 过滤出实际存在于 merged_df 中的列
            cols_to_fill = [c for c in att_cols if c in merged_df.columns]
            if cols_to_fill:
                merged_df[cols_to_fill] = merged_df[cols_to_fill].ffill().fillna(0)

        # 恢复 datetime 列 (有些下游逻辑可能依赖它作为列存在)
        merged_df.reset_index(inplace=True)
        
        return merged_df
