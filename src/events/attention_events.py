from dataclasses import dataclass
from typing import List, Optional
import pandas as pd
from src.config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR


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
    path = PROCESSED_DATA_DIR / f"attention_features_{symbol.lower()}.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True, errors='coerce')
    df = df.dropna(subset=['datetime'])
    if start:
        df = df[df['datetime'] >= start]
    if end:
        df = df[df['datetime'] <= end]

    # 计算 rolling 分位数阈值
    def q_threshold(s: pd.Series) -> pd.Series:
        return s.rolling(lookback_days, min_periods=5).apply(lambda x: pd.Series(x).quantile(min_quantile), raw=False)

    df['att_q'] = q_threshold(df['attention_score'])
    df['w_q'] = q_threshold(df.get('weighted_attention', pd.Series(index=df.index, dtype=float).fillna(0)))
    df['bull_q'] = q_threshold(df.get('bullish_attention', pd.Series(index=df.index, dtype=float).fillna(0)))
    df['bear_q'] = q_threshold(df.get('bearish_attention', pd.Series(index=df.index, dtype=float).fillna(0)))

    events: List[AttentionEvent] = []
    for _, row in df.iterrows():
        dt = row['datetime']
        summ = f"news_count={int(row.get('news_count', 0))}, att={row.get('attention_score', 0):.1f}, w_att={row.get('weighted_attention', 0):.2f}"
        # spike: attention_score 超过分位数
        if pd.notna(row['att_q']) and row['attention_score'] >= row['att_q']:
            events.append(AttentionEvent(dt, 'attention_spike', float(row['attention_score'] - row['att_q']), summ))
        # high_weighted_event
        if pd.notna(row['w_q']) and row.get('weighted_attention', 0) >= row['w_q']:
            events.append(AttentionEvent(dt, 'high_weighted_event', float(row['weighted_attention'] - row['w_q']), summ))
        # high_bullish
        if pd.notna(row['bull_q']) and row.get('bullish_attention', 0) >= row['bull_q']:
            events.append(AttentionEvent(dt, 'high_bullish', float(row['bullish_attention'] - row['bull_q']), summ))
        # high_bearish
        if pd.notna(row['bear_q']) and row.get('bearish_attention', 0) >= row['bear_q']:
            events.append(AttentionEvent(dt, 'high_bearish', float(row['bearish_attention'] - row['bear_q']), summ))
        # event_intensity
        if int(row.get('event_intensity', 0)) == 1:
            events.append(AttentionEvent(dt, 'event_intensity', 1.0, summ))

    return events
