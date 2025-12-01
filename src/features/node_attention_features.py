import pandas as pd
from typing import Optional

from src.data.db_storage import load_news_data, USE_DATABASE, get_db
from src.features.news_features import (
    source_weight,
    sentiment_score,
    relevance_flag,
    extract_tags,
)


def _build_node_id(row: pd.Series) -> str:
    """构造节点唯一 ID。

    当前约定：
    - platform: 平台类别，如 "news" / "social" / "rss"。
    - node: 传播节点名称，优先使用 author/account，其次 source。
    - node_id: f"{platform}:{node}"。

    注意：此规则需与抓取层 `attention_fetcher` 中的约定保持一致。
    """

    platform = row.get("platform") or "news"
    author = row.get("author")
    source = row.get("source") or "Unknown"
    node = author or row.get("node") or source
    return f"{platform}:{node}"


def build_node_attention_features(symbol: str, freq: str = "D") -> pd.DataFrame:
    """构建节点级注意力特征表。

    返回列包括：
    - symbol, node_id, datetime, freq
    - news_count, weighted_attention, bullish_attention, bearish_attention
    - sentiment_mean, sentiment_std
    """

    # 从数据库或 CSV 加载新闻数据
    df = load_news_data(symbol, start=None, end=None, limit=None)
    if df.empty:
        return pd.DataFrame(columns=[
            "symbol",
            "node_id",
            "datetime",
            "freq",
            "news_count",
            "weighted_attention",
            "bullish_attention",
            "bearish_attention",
            "sentiment_mean",
            "sentiment_std",
        ])

    if "datetime" not in df.columns:
        return pd.DataFrame()

    df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"])

    # 基本新闻级特征补全
    if "source_weight" not in df.columns:
        df["source_weight"] = df.get("source", "Unknown").astype(str).apply(source_weight)
    if "sentiment_score" not in df.columns:
        df["sentiment_score"] = df.get("title", "").astype(str).apply(sentiment_score)
    if "relevance" not in df.columns:
        df["relevance"] = df.get("title", "").astype(str).apply(lambda t: relevance_flag(str(t), symbol=symbol))
    if "tags" not in df.columns:
        df["tags"] = df.get("title", "").astype(str).apply(lambda t: ",".join(extract_tags(str(t))))

    # 节点 ID
    df["node_id"] = df.apply(_build_node_id, axis=1)

    # relevance 权重: direct=1.0, related=0.5
    rel_w = df["relevance"].map({"direct": 1.0, "related": 0.5}).fillna(0.5)
    df["weighted_score"] = df["source_weight"] * rel_w

    weighted = df["weighted_score"]
    df["bullish_component"] = (df["sentiment_score"].clip(lower=0)) * weighted
    df["bearish_component"] = (-df["sentiment_score"].clip(upper=0)) * weighted

    df = df.set_index("datetime")

    # 节点 + 时间聚合
    grp = (
        df.groupby("node_id")
        .resample(freq)
        .agg(
            news_count=("title", "count"),
            weighted_attention=("weighted_score", "sum"),
            bullish_attention=("bullish_component", "sum"),
            bearish_attention=("bearish_component", "sum"),
            sentiment_mean=("sentiment_score", "mean"),
            sentiment_std=("sentiment_score", "std"),
        )
        .reset_index()
    )

    grp["symbol"] = symbol
    grp["freq"] = freq

    # 规范列顺序
    cols = [
        "symbol",
        "node_id",
        "datetime",
        "freq",
        "news_count",
        "weighted_attention",
        "bullish_attention",
        "bearish_attention",
        "sentiment_mean",
        "sentiment_std",
    ]
    grp = grp[cols].sort_values(["node_id", "datetime"]).reset_index(drop=True)

    # 可选：直接写入数据库/CSV，由上层调用决定，此处仅返回 DataFrame
    return grp


def save_node_attention_features(df: pd.DataFrame) -> None:
    """将节点级注意力特征持久化。

    - 强制写入专用表 `node_attention_features`（由 ORM 管理）。
    """

    if df.empty:
        return

    # 强制使用数据库
    db = get_db()
    from src.database.models import NodeAttentionFeature  # type: ignore
    from src.database.models import get_session

    session = get_session(db.engine)
    try:
        records = df.to_dict("records")
        objects = []
        for rec in records:
            # 使用 from_record 处理类型转换和默认值
            obj = NodeAttentionFeature.from_record(rec)
            objects.append(obj)
        if objects:
            # 使用 merge 避免主键冲突
            for obj in objects:
                session.merge(obj)
            session.commit()
    except Exception as e:
        session.rollback()
        raise RuntimeError(f"Failed to save node attention features to DB: {e}")
    finally:
        session.close()
