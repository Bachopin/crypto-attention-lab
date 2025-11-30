from dataclasses import dataclass
from typing import Optional, List

import pandas as pd
import numpy as np

from src.data.db_storage import load_price_data, USE_DATABASE, get_db
from src.features.node_attention_features import build_node_attention_features
from src.services.attention_service import AttentionService


@dataclass
class NodeCarryFactor:
    symbol: str
    node_id: str
    n_events: int
    mean_excess_return: float
    hit_rate: float
    ir: float
    lookahead: str
    lookback_days: int
    updated_at: pd.Timestamp


def compute_node_carry_factor(
    symbol: str,
    lookahead: str = "1d",
    lookback_days: int = 365,
    start: Optional[pd.Timestamp] = None,
    end: Optional[pd.Timestamp] = None,
    chunk_days: Optional[int] = None,
) -> pd.DataFrame:
    """计算节点带货能力因子。

    步骤：
    1. 使用 `detect_attention_events` 获取标的级注意力事件；
    2. 构建节点级注意力特征，识别在事件当日有贡献的节点；
    3. 基于日线价格，计算事件后 lookahead 窗口的对数收益；
    4. 按节点聚合，得到 mean_excess_return、hit_rate、IR 等指标。

    说明：
    - 当前实现中，节点的收益基于“事件当天收盘价 → 未来 N 日收盘价”的对数收益；
    - 超额收益（excess）暂时以 0 作为基准，即 mean_excess_return 即为平均绝对收益，
      未来可扩展为减去基准组合或无事件样本的平均收益。
    """

    # 解析 lookahead，当前仅支持日级，如 "1d"、"3d"
    if not lookahead.endswith("d"):
        raise ValueError("lookahead currently supports only day-based horizons, e.g. '1d'")
    horizon_days = int(lookahead[:-1])
    if horizon_days <= 0:
        raise ValueError("lookahead days must be positive")

    # 价格数据（1d 收盘）
    price_df, _ = load_price_data(f"{symbol}USDT", "1d", start, end)
    if price_df.empty:
        return pd.DataFrame()
    price_df = price_df.sort_values("datetime").reset_index(drop=True)
    price_df["datetime"] = pd.to_datetime(price_df["datetime"], utc=True)

    # 注意力事件（按标的）
    events = AttentionService.get_attention_events(symbol=symbol, lookback_days=lookback_days, start=start, end=end)
    if not events:
        return pd.DataFrame()

    events_df = pd.DataFrame({
        "datetime": [pd.to_datetime(e.datetime, utc=True).normalize() for e in events],
        "event_type": [e.event_type for e in events],
    })

    # 节点级注意力特征（日级）
    node_feat = build_node_attention_features(symbol=symbol, freq="D")
    if node_feat.empty:
        return pd.DataFrame()

    node_feat["datetime"] = pd.to_datetime(node_feat["datetime"], utc=True).dt.normalize()

    # 只保留在事件当日有活动的节点
    merged = node_feat.merge(events_df, on="datetime", how="inner")
    if merged.empty:
        return pd.DataFrame()

    # 价格索引映射
    price_df["date"] = price_df["datetime"].dt.normalize()
    price_df = price_df.reset_index(drop=True)

    # 为每个事件 + 节点计算未来收益
    # 如果后续需要分块计算以降低内存占用，可按 chunk_days 对事件进行分组并分批处理。
    # 这里先提供占位参数与说明，当前实现仍一次性处理。
    rows = []
    for _, row in merged.iterrows():
        ev_date = row["datetime"]
        node_id = row["node_id"]

        # 找到事件当日价格索引
        idx_list = price_df.index[price_df["date"] == ev_date].tolist()
        if not idx_list:
            continue
        base_idx = idx_list[0]
        exit_idx = base_idx + horizon_days
        if exit_idx >= len(price_df):
            continue

        base_price = float(price_df.loc[base_idx, "close"])
        exit_price = float(price_df.loc[exit_idx, "close"])
        if base_price <= 0 or exit_price <= 0:
            continue

        # 对数收益
        ret = float(np.log(exit_price / base_price))

        rows.append({
            "symbol": symbol,
            "node_id": node_id,
            "event_date": ev_date,
            "return": ret,
        })

    if not rows:
        return pd.DataFrame()

    ret_df = pd.DataFrame(rows)

    # 节点维度聚合
    grp = ret_df.groupby(["symbol", "node_id"])  # type: ignore[call-arg]
    stats = grp["return"].agg([
        ("mean_return", "mean"),
        ("std_return", "std"),
        ("hit_rate", lambda x: (x > 0).mean()),
        ("n_events", "count"),
    ]).reset_index()

    # 信息比率 IR = mean / std
    stats["ir"] = stats.apply(
        lambda r: float(r["mean_return"]) / float(r["std_return"]) if r["std_return"] not in (0, None, float("nan")) else 0.0,
        axis=1,
    )

    stats["mean_excess_return"] = stats["mean_return"]  # 暂时等于平均收益
    stats["lookahead"] = lookahead
    stats["lookback_days"] = lookback_days
    # pd.Timestamp.utcnow() 已为 tz-naive，需本地化为 UTC；若为 tz-aware 则使用 tz_convert
    ts_now = pd.Timestamp.utcnow()
    if ts_now.tzinfo is None:
        stats["updated_at"] = ts_now.tz_localize("UTC")
    else:
        stats["updated_at"] = ts_now.tz_convert("UTC")

    # 规范列
    out_cols = [
        "symbol",
        "node_id",
        "n_events",
        "mean_excess_return",
        "hit_rate",
        "ir",
        "lookahead",
        "lookback_days",
        "updated_at",
    ]
    out = stats[[
        "symbol",
        "node_id",
        "n_events",
        "mean_excess_return",
        "hit_rate",
        "ir",
        "lookahead",
        "lookback_days",
        "updated_at",
    ]].copy()

    return out


def save_node_carry_factors(df: pd.DataFrame) -> None:
    """将节点带货能力因子结果持久化。

    - 数据库模式：写入 `node_carry_factors` 表；
    - 非数据库模式：写入 `data/processed/node_carry_factors_{symbol}.csv`。
    """

    if df.empty:
        return

    from src.config.settings import PROCESSED_DATA_DIR

    # 清理异常值，避免 NaN/Inf 导致数据库约束错误
    df = df.copy()
    df.replace([np.nan, np.inf, -np.inf], 0.0, inplace=True)

    if USE_DATABASE:
        db = get_db()
        from src.database.models import NodeCarryFactorModel  # type: ignore
        from src.database.models import get_session

        session = get_session(db.engine)
        try:
            records = df.to_dict("records")
            objects: List[NodeCarryFactorModel] = []
            for rec in records:
                obj = NodeCarryFactorModel.from_record(rec)  # 需在 models 中实现
                objects.append(obj)
            if objects:
                session.bulk_save_objects(objects)
                session.commit()
        finally:
            session.close()
    else:
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        for sym, sub in df.groupby("symbol"):
            path = PROCESSED_DATA_DIR / f"node_carry_factors_{sym.lower()}.csv"
            sub.to_csv(path, index=False)


def load_node_carry_factors(symbol: Optional[str] = None) -> pd.DataFrame:
    """加载节点带货能力因子。

    - symbol 为 None 时返回所有标的；
    - 在 CSV 模式下，将合并所有文件后再按 symbol 过滤。
    """

    from src.config.settings import PROCESSED_DATA_DIR

    if USE_DATABASE:
        db = get_db()
        from src.database.models import NodeCarryFactorModel  # type: ignore
        from src.database.models import get_session

        session = get_session(db.engine)
        try:
            query = session.query(NodeCarryFactorModel)
            if symbol:
                query = query.filter(NodeCarryFactorModel.symbol == symbol)
            rows = query.all()
            if not rows:
                return pd.DataFrame()

            return pd.DataFrame([
                {
                    "symbol": r.symbol,
                    "node_id": r.node_id,
                    "n_events": r.n_events,
                    "mean_excess_return": r.mean_excess_return,
                    "hit_rate": r.hit_rate,
                    "ir": r.ir,
                    "lookahead": r.lookahead,
                    "lookback_days": r.lookback_days,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ])
        finally:
            session.close()
    else:
        frames: List[pd.DataFrame] = []
        for path in PROCESSED_DATA_DIR.glob("node_carry_factors_*.csv"):
            sub = pd.read_csv(path)
            frames.append(sub)
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True)
        if symbol:
            df = df[df["symbol"] == symbol]
        return df
