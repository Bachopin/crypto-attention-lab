import os
import time
import pandas as pd
from typing import Optional, List, Tuple, Dict
from datetime import datetime

from src.data.db_storage import get_db


class FeatureService:
    """
    预存特征读取服务：统一从 attention_features 表批量拉取需要的列，
    支持列白名单与简单内存缓存，便于回测/情景分析优先复用数据库中的预计算结果。
    """

    # 简单内存缓存（可选，默认启用）
    _cache: Dict[Tuple[str, str, Optional[str], Optional[str], Tuple[str, ...]], Tuple[float, pd.DataFrame]] = {}
    _cache_ttl_seconds: int = int(os.getenv('FEATURE_CACHE_TTL', '60'))

    @staticmethod
    def load_precomputed_features(
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        timeframe: str = 'D',
        columns: Optional[List[str]] = None,
        fillna_zero: bool = False,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        从 attention_features 读取预存特征。

        - symbol: 币种（如 'BTC' 或 'BTCUSDT'，内部会统一为无 USDT 后缀）
        - start/end: 时间范围（UTC）
        - timeframe: 'D'（日级）或 '4H'（4小时级）
        - columns: 需要的列白名单（自动包含 'datetime' / 'timeframe'）
        - fillna_zero: 是否将缺失值填 0（默认 False）
        - use_cache: 是否使用 60s 简单内存缓存
        """
        # 规范 symbol（attention 表使用无 USDT 后缀的 symbol）
        sym = symbol.upper()
        if sym.endswith('USDT'):
            sym = sym[:-4]

        cols_tuple: Tuple[str, ...] = tuple(sorted(columns)) if columns else tuple()
        key = (sym, timeframe, start.isoformat() if start else None, end.isoformat() if end else None, cols_tuple)

        # 命中缓存
        if use_cache and key in FeatureService._cache:
            ts, df_cached = FeatureService._cache[key]
            if time.time() - ts <= FeatureService._cache_ttl_seconds:
                return df_cached.copy()
            else:
                FeatureService._cache.pop(key, None)

        db = get_db()
        df = db.get_attention_features(sym, start, end, timeframe)
        if df is None or df.empty:
            return pd.DataFrame()

        # 列裁剪（保留 datetime 与 timeframe）
        if columns:
            keep = ['datetime', 'timeframe'] + [c for c in columns if c in df.columns]
            # 去重保持顺序
            seen = set()
            ordered_keep = []
            for c in keep:
                if c not in seen and c in df.columns:
                    seen.add(c)
                    ordered_keep.append(c)
            df = df[ordered_keep].copy()

        # 统一类型与填充
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        if fillna_zero:
            df = df.fillna(0)

        if use_cache:
            FeatureService._cache[key] = (time.time(), df.copy())

        return df
