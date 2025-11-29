from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
from src.config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from src.data.db_storage import load_attention_data


@dataclass
class AttentionEvent:
    datetime: pd.Timestamp
    event_type: str
    intensity: float
    summary: str


def detect_attention_events(
    symbol: str = "ZEC",
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
    lookback_days: int = 30,
    min_quantile: float = 0.8,
) -> List[AttentionEvent]:
    # 数据库优先加载
    df = load_attention_data(symbol, start, end)
    if df.empty:
        return []
    df = df.dropna(subset=['datetime'])

    # 计算 rolling 分位数阈值（更严格的 min_periods，避免初期全 0 导致噪声）
    def q_threshold(s: pd.Series) -> pd.Series:
        return s.rolling(lookback_days, min_periods=max(10, lookback_days // 2)).apply(
            lambda x: pd.Series(x).quantile(min_quantile), raw=False
        )

    # 首选合成注意力作为 spike 基础；回退到 legacy attention_score
    base_spike_series = df.get('composite_attention_score', df['attention_score']).copy()
    df['att_base'] = base_spike_series.fillna(0)
    df['att_q'] = q_threshold(df['att_base'])
    df['w_q'] = q_threshold(df.get('weighted_attention', pd.Series(index=df.index, dtype=float).fillna(0)))
    df['bull_q'] = q_threshold(df.get('bullish_attention', pd.Series(index=df.index, dtype=float).fillna(0)))
    df['bear_q'] = q_threshold(df.get('bearish_attention', pd.Series(index=df.index, dtype=float).fillna(0)))

    events: List[AttentionEvent] = []
    eps = 1e-9
    for _, row in df.iterrows():
        dt = row['datetime']
        summ = (
            f"news_count={int(row.get('news_count', 0))}, "
            f"att_base={row.get('att_base', 0):.3f}, w_att={row.get('weighted_attention', 0):.3f}"
        )
        # spike: 使用合成注意力（或回退）且严格大于阈值，并且当前值需为正
        att_val = float(row.get('att_base', 0) or 0)
        att_q = row.get('att_q')
        if pd.notna(att_q) and att_val > max(float(att_q), eps):
            events.append(AttentionEvent(dt, 'attention_spike', float(att_val - float(att_q)), summ))
        # high_weighted_event: 权重注意力严格大于阈值，且为正
        w_val = float(row.get('weighted_attention', 0) or 0)
        w_q = row.get('w_q')
        if pd.notna(w_q) and w_val > max(float(w_q), eps):
            events.append(AttentionEvent(dt, 'high_weighted_event', float(w_val - float(w_q)), summ))
        # high_bullish: bullish_attention high AND > bearish_attention
        bull_val = float(row.get('bullish_attention', 0) or 0)
        bear_val = float(row.get('bearish_attention', 0) or 0)
        bull_q = row.get('bull_q')
        if pd.notna(bull_q) and bull_val > max(float(bull_q), eps) and bull_val > bear_val:
            events.append(AttentionEvent(dt, 'high_bullish', float(bull_val - float(bull_q)), summ))
        # high_bearish: bearish_attention high AND > bullish_attention
        bear_q = row.get('bear_q')
        if pd.notna(bear_q) and bear_val > max(float(bear_q), eps) and bear_val > bull_val:
            events.append(AttentionEvent(dt, 'high_bearish', float(bear_val - float(bear_q)), summ))
        # event_intensity
        if int(row.get('event_intensity', 0)) == 1:
            events.append(AttentionEvent(dt, 'event_intensity', 1.0, summ))

    return events
