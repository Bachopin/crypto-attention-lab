from dataclasses import dataclass
from typing import List, Dict, Sequence
import pandas as pd

from src.data.db_storage import load_price_data, load_attention_data
from src.events.attention_events import detect_attention_events, AttentionEvent


@dataclass
class EventPerformance:
    event_type: str
    lookahead_days: int
    avg_return: float
    sample_size: int


def compute_event_performance(
    symbol: str,
    lookahead_days: Sequence[int],
    event_types: Sequence[str] | None = None,
) -> Dict[str, Dict[int, EventPerformance]]:
    """计算事件后的平均收益表现。

    返回结构:
        {event_type: {lookahead: EventPerformance, ...}, ...}
    """
    if not lookahead_days:
        return {}

    # 统一为 list[int]
    horizons = sorted({int(d) for d in lookahead_days if int(d) > 0})
    if not horizons:
        return {}

    # 加载日线价格和注意力事件
    p_df, _ = load_price_data(f"{symbol}USDT", "1d", None, None)
    if p_df.empty:
        return {}

    p_df = p_df.sort_values("datetime").reset_index(drop=True)
    p_df["datetime"] = pd.to_datetime(p_df["datetime"])

    events: List[AttentionEvent] = detect_attention_events(symbol=symbol)
    if not events:
        return {}

    if event_types is not None:
        event_types_set = set(event_types)
        events = [e for e in events if e.event_type in event_types_set]

    # 方便索引
    dt_to_idx: Dict[pd.Timestamp, int] = {
        pd.to_datetime(row["datetime"]): idx for idx, row in p_df.iterrows()
    }

    # 初始化结果容器
    result: Dict[str, Dict[int, EventPerformance]] = {}

    for e in events:
        etype = e.event_type
        if etype not in result:
            result[etype] = {h: EventPerformance(etype, h, 0.0, 0) for h in horizons}

        # 找到事件当天在价格序列中的索引（按日期对齐）
        event_dt = pd.to_datetime(e.datetime).normalize()
        # 找到价格数据中同一天的索引（按日期忽略时间）
        idx_candidates = [idx for idx, row in p_df.iterrows() if pd.to_datetime(row["datetime"]).normalize() == event_dt]
        if not idx_candidates:
            continue
        base_idx = idx_candidates[0]

        base_price = float(p_df.loc[base_idx, "close"])
        if base_price <= 0:
            continue

        for h in horizons:
            exit_idx = base_idx + h
            if exit_idx >= len(p_df):
                continue
            exit_price = float(p_df.loc[exit_idx, "close"])
            ret = exit_price / base_price - 1.0

            perf = result[etype][h]
            # 在线增量更新平均值: new_avg = old_avg + (x - old_avg) / n
            n_new = perf.sample_size + 1
            avg_new = perf.avg_return + (ret - perf.avg_return) / n_new
            perf.avg_return = avg_new
            perf.sample_size = n_new

    return result
