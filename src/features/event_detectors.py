"""
Feature logic for detecting attention events.
Pure calculation logic, no database access.
"""
from dataclasses import dataclass
from typing import List, Optional
import json
import pandas as pd
from src.utils.math_utils import compute_rolling_quantile

@dataclass
class AttentionEvent:
    datetime: pd.Timestamp
    event_type: str
    intensity: float
    summary: str
    
    def to_dict(self) -> dict:
        """转换为可 JSON 序列化的字典"""
        return {
            "event_type": self.event_type,
            "intensity": self.intensity,
            "summary": self.summary,
        }
    
    @classmethod
    def from_dict(cls, dt: pd.Timestamp, d: dict) -> "AttentionEvent":
        """从字典恢复事件对象"""
        return cls(
            datetime=dt,
            event_type=d.get("event_type", ""),
            intensity=float(d.get("intensity", 0)),
            summary=d.get("summary", ""),
        )


def events_to_json(events: List[AttentionEvent]) -> Optional[str]:
    """将事件列表序列化为 JSON 字符串（用于存储到数据库）"""
    if not events:
        return None
    return json.dumps([e.to_dict() for e in events])


def events_from_json(dt: pd.Timestamp, json_str: Optional[str]) -> List[AttentionEvent]:
    """从 JSON 字符串恢复事件列表"""
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
        return [AttentionEvent.from_dict(dt, d) for d in data]
    except (json.JSONDecodeError, TypeError):
        return []

def detect_attention_spikes(
    df: pd.DataFrame,
    lookback_days: int = 30,
    min_quantile: float = 0.8,
) -> List[AttentionEvent]:
    """
    Pure logic function to detect attention events from a DataFrame.
    
    Args:
        df: DataFrame containing attention metrics. Must have 'datetime' column.
            Expected columns: 'composite_attention_score' (or 'attention_score'),
            'weighted_attention', 'bullish_attention', 'bearish_attention', 'event_intensity'.
        lookback_days: Window size for quantile calculation.
        min_quantile: Quantile threshold (e.g., 0.8 for 80th percentile).
        
    Returns:
        List of AttentionEvent objects.
    """
    if df.empty:
        return []
        
    # Ensure we work on a copy to avoid modifying the input
    df = df.copy()
    
    # Ensure datetime column exists
    if 'datetime' not in df.columns:
        # If index is datetime, reset index
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df = df.rename(columns={'index': 'datetime'}) # Handle unnamed index
        else:
            # Cannot proceed without datetime
            return []

    # Helper for quantile threshold using shared math util
    def q_threshold(s: pd.Series) -> pd.Series:
        return compute_rolling_quantile(s, lookback_days, min_quantile)

    # 首选合成注意力作为 spike 基础；回退到 legacy attention_score
    base_spike_series = df.get('composite_attention_score', df.get('attention_score', pd.Series(index=df.index, dtype=float))).copy()
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


def detect_events_per_row(
    df: pd.DataFrame,
    lookback_days: int = 30,
    min_quantile: float = 0.8,
) -> pd.DataFrame:
    """
    检测事件并返回带有 detected_events 列的 DataFrame。
    
    用于在特征计算时同时计算事件并存储到数据库。
    
    Args:
        df: 包含注意力特征的 DataFrame
        lookback_days: 滚动窗口天数
        min_quantile: 分位数阈值
        
    Returns:
        带有 detected_events 列的 DataFrame（JSON 字符串格式）
    """
    if df.empty:
        return df
        
    df = df.copy()
    
    # Ensure datetime column exists
    if 'datetime' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df = df.rename(columns={'index': 'datetime'})
        else:
            df['detected_events'] = None
            return df

    # Helper for quantile threshold
    def q_threshold(s: pd.Series) -> pd.Series:
        return compute_rolling_quantile(s, lookback_days, min_quantile)

    # 计算阈值
    base_spike_series = df.get('composite_attention_score', df.get('attention_score', pd.Series(index=df.index, dtype=float))).copy()
    df['_att_base'] = base_spike_series.fillna(0)
    df['_att_q'] = q_threshold(df['_att_base'])
    df['_w_q'] = q_threshold(df.get('weighted_attention', pd.Series(index=df.index, dtype=float).fillna(0)))
    df['_bull_q'] = q_threshold(df.get('bullish_attention', pd.Series(index=df.index, dtype=float).fillna(0)))
    df['_bear_q'] = q_threshold(df.get('bearish_attention', pd.Series(index=df.index, dtype=float).fillna(0)))

    eps = 1e-9
    detected_events_list = []
    
    for idx, row in df.iterrows():
        dt = row['datetime']
        row_events: List[AttentionEvent] = []
        
        summ = (
            f"news_count={int(row.get('news_count', 0))}, "
            f"att_base={row.get('_att_base', 0):.3f}, w_att={row.get('weighted_attention', 0):.3f}"
        )
        
        # attention_spike
        att_val = float(row.get('_att_base', 0) or 0)
        att_q = row.get('_att_q')
        if pd.notna(att_q) and att_val > max(float(att_q), eps):
            row_events.append(AttentionEvent(dt, 'attention_spike', float(att_val - float(att_q)), summ))
        
        # high_weighted_event
        w_val = float(row.get('weighted_attention', 0) or 0)
        w_q = row.get('_w_q')
        if pd.notna(w_q) and w_val > max(float(w_q), eps):
            row_events.append(AttentionEvent(dt, 'high_weighted_event', float(w_val - float(w_q)), summ))
        
        # high_bullish
        bull_val = float(row.get('bullish_attention', 0) or 0)
        bear_val = float(row.get('bearish_attention', 0) or 0)
        bull_q = row.get('_bull_q')
        if pd.notna(bull_q) and bull_val > max(float(bull_q), eps) and bull_val > bear_val:
            row_events.append(AttentionEvent(dt, 'high_bullish', float(bull_val - float(bull_q)), summ))
        
        # high_bearish
        bear_q = row.get('_bear_q')
        if pd.notna(bear_q) and bear_val > max(float(bear_q), eps) and bear_val > bull_val:
            row_events.append(AttentionEvent(dt, 'high_bearish', float(bear_val - float(bear_q)), summ))
        
        # event_intensity
        if int(row.get('event_intensity', 0)) == 1:
            row_events.append(AttentionEvent(dt, 'event_intensity', 1.0, summ))
        
        detected_events_list.append(events_to_json(row_events))
    
    df['detected_events'] = detected_events_list
    
    # 清理临时列
    df = df.drop(columns=['_att_base', '_att_q', '_w_q', '_bull_q', '_bear_q'], errors='ignore')
    
    return df
