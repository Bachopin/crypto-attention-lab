import pandas as pd
import numpy as np
from typing import List, Optional, Dict, Any
from datetime import datetime
from src.data.db_storage import load_attention_data, load_price_data

def analyze_attention_regimes(
    symbols: List[str],
    lookahead_days: List[int],
    attention_source: str = "composite",
    split_method: str = "quantile",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    对每个 symbol，按 attention regime 分析未来收益等统计。
    返回结构: {symbol: {regime: {lookahead: {mean, std, pos_ratio, max_drawdown, ...}}}}
    """
    results = {}
    for symbol in symbols:
        # 1. 加载数据
        attn_df = load_attention_data(symbol, start, end)
        price_df = load_price_data(symbol, timeframe="1d", start=start, end=end)
        if attn_df is None or price_df is None or len(attn_df) == 0 or len(price_df) == 0:
            results[symbol] = {"error": "No data"}
            continue
        # 2. 选择 attention 指标
        if attention_source == "composite":
            attn_col = "composite_attention_score"
        elif attention_source == "news_channel":
            attn_col = "news_channel_score"
        else:
            attn_col = attention_source
        if attn_col not in attn_df.columns:
            results[symbol] = {"error": f"No column {attn_col}"}
            continue
        # 3. 合并数据
        df = pd.merge(attn_df[["datetime", attn_col]], price_df[["datetime", "close"]], on="datetime", how="inner")
        df = df.sort_values("datetime").reset_index(drop=True)
        # 4. regime 分段
        if split_method == "quantile":
            q = df[attn_col].quantile([0.33, 0.66]).values
            bins = [-np.inf, q[0], q[1], np.inf]
            labels = ["low", "mid", "high"]
            df["regime"] = pd.cut(df[attn_col], bins=bins, labels=labels, include_lowest=True)
        else:
            # fallback: median split
            m = df[attn_col].median()
            bins = [-np.inf, m, np.inf]
            labels = ["low", "high"]
            df["regime"] = pd.cut(df[attn_col], bins=bins, labels=labels, include_lowest=True)
        # 5. 计算未来收益
        df["log_close"] = np.log(df["close"])
        for k in lookahead_days:
            df[f"fwd_return_{k}d"] = df["log_close"].shift(-k) - df["log_close"]
        # 6. regime 统计
        symbol_result = {}
        for regime in df["regime"].dropna().unique():
            regime_result = {}
            sub = df[df["regime"] == regime]
            for k in lookahead_days:
                ret = sub[f"fwd_return_{k}d"].dropna()
                if len(ret) == 0:
                    stats = {"mean": None, "std": None, "median": None, "pos_ratio": None, "max_drawdown": None, "count": 0}
                else:
                    # 最大回撤（基于累计收益）
                    cum = ret.cumsum()
                    drawdown = cum - cum.cummax()
                    max_dd = drawdown.min() if len(drawdown) > 0 else None
                    stats = {
                        "mean": ret.mean(),
                        "std": ret.std(),
                        "median": ret.median(),
                        "pos_ratio": (ret > 0).mean(),
                        "max_drawdown": max_dd,
                        "count": len(ret),
                    }
                regime_result[str(k)] = stats
            symbol_result[str(regime)] = regime_result
        results[symbol] = {
            "regimes": list(df["regime"].dropna().unique()),
            "lookahead_days": lookahead_days,
            "stats": symbol_result,
        }
    return results
