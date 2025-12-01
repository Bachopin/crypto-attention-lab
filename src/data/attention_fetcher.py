import os
import requests
import pandas as pd
import random
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from src.config.settings import RAW_DATA_DIR


# ==============================================================================
# 废弃警告：此模块中的函数仅获取 ZEC 相关新闻，已被更完善的实现替代。
#
# 新的新闻获取流程：
# - 使用 scripts/fetch_news_data.py 获取所有加密货币新闻（全局获取，按 URL 去重）
# - 新闻存储在数据库中，通过 symbols 字段标记涉及的代币
# - Attention 计算时使用 src/data/db_storage.load_news_data(symbol, start, end) 
#   按代币符号和时间过滤新闻
#
# 此模块保留仅为兼容旧代码，请勿在新代码中使用。
# ==============================================================================


def _dt_or_default(value, default_days=365):
    if value is None:
        return datetime.now(timezone.utc) - timedelta(days=default_days)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _fetch_from_cryptopanic(since: datetime, until: datetime) -> list[dict]:
    token = os.getenv("CRYPTOPANIC_API_KEY") or os.getenv("CRYPTOPANIC_TOKEN")
    if not token:
        return []
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        "auth_token": token,
        "currencies": "ZEC",
        "kind": "news",
        "public": "true",
    }
    out: list[Dict[str, Any]] = []
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("results", []):
            created = item.get("published_at") or item.get("created_at")
            if not created:
                continue
            dt = pd.to_datetime(created, utc=True)
            if not (since <= dt.to_pydatetime() <= until):
                continue
            title = (item.get("title") or "").strip()
            url_ = item.get("url") or (item.get("source") or {}).get("url") or ""
            source = (item.get("source") or {}).get("title") or (item.get("domain") or "CryptoPanic")

            # 平台与节点信息
            # 当前约定：
            # - platform: 数据源平台类型，如 "news"（CryptoPanic 新闻聚合）、未来可扩展为 "social" 等
            # - node: 传播节点标识（例如具体媒体或账号）。此处使用 source 作为节点名。
            # - node_id: 节点唯一 ID，当前规则为 f"{platform}:{source}"。
            platform = "news"
            node = source
            node_id = f"{platform}:{node}"

            out.append({
                "timestamp": int(dt.value // 10**6),  # ms
                "datetime": dt.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S"),
                "title": title,
                "source": source,
                "url": url_,
                "platform": platform,
                "author": None,
                "node": node,
                "node_id": node_id,
                "language": "en",  # CryptoPanic 不提供语种，默认英文。TODO: 结合内容检测。
            })
    except Exception:
        return []
    return out


def _fetch_from_newsapi(since: datetime, until: datetime) -> list[dict]:
    api_key = os.getenv("NEWS_API_KEY") or os.getenv("NEWSAPI_KEY")
    if not api_key:
        return []
    # NewsAPI everything endpoint
    url = "https://newsapi.org/v2/everything"
    # 关键词尽量覆盖 Zcash/ZEC，避免误报
    q = "(Zcash OR ZEC)"
    params = {
        "q": q,
        "language": "en",
        "sortBy": "publishedAt",
        "from": since.isoformat(),
        "to": until.isoformat(),
        "pageSize": 100,
        "apiKey": api_key,
    }
    out: list[Dict[str, Any]] = []
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for art in data.get("articles", []):
            dt_raw = art.get("publishedAt")
            if not dt_raw:
                continue
            dt = pd.to_datetime(dt_raw, utc=True)
            title = (art.get("title") or "").strip()
            url_ = art.get("url") or ""
            source = (art.get("source") or {}).get("name") or "NewsAPI"

            platform = "news"
            # NewsAPI 提供 author 字段，可能是记者或账号名
            author = (art.get("author") or None) or None
            node = author or source
            node_id = f"{platform}:{node}"
            out.append({
                "timestamp": int(dt.value // 10**6),
                "datetime": dt.tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S"),
                "title": title,
                "source": source,
                "url": url_,
                "platform": platform,
                "author": author,
                "node": node,
                "node_id": node_id,
                "language": (art.get("language") or "en"),
            })
    except Exception:
        return []
    return out


def _fetch_mock(since: datetime, until: datetime) -> list[dict]:
    news_list = []
    current_date = since
    while current_date <= until:
        daily_news_count = random.randint(0, 5)
        for _ in range(daily_news_count):
            source = random.choice(["CoinDesk", "Twitter", "CryptoSlate", "Medium"])
            platform = "social" if source == "Twitter" else "news"
            node = source
            node_id = f"{platform}:{node}"
            news_item = {
                "timestamp": int(current_date.timestamp() * 1000),
                "datetime": current_date.strftime("%Y-%m-%d %H:%M:%S"),
                "title": f"ZEC News Sample {random.randint(1000, 9999)}",
                "source": source,
                "url": "https://example.com/news",
                "platform": platform,
                "author": None,
                "node": node,
                "node_id": node_id,
                "language": "en",
            }
            news_list.append(news_item)
        current_date += timedelta(days=1)
    return news_list


def fetch_zec_news(since: Optional[datetime] = None, until: Optional[datetime] = None) -> list[dict]:
    """
    获取 ZEC/Zcash 相关新闻：优先 CryptoPanic，其次 NewsAPI；都不可用时使用 Mock。
    返回标准字段：timestamp(ms), datetime(str, UTC), title, source, url
    
    .. deprecated::
        此函数仅获取 ZEC 相关新闻，已废弃。
        请使用 scripts/fetch_news_data.py 全局获取新闻，
        然后通过 src/data/db_storage.load_news_data(symbol, start, end) 按代币过滤。
    """
    warnings.warn(
        "fetch_zec_news is deprecated. Use scripts/fetch_news_data.py for global news fetching, "
        "and src/data/db_storage.load_news_data(symbol, start, end) for symbol-filtered queries.",
        DeprecationWarning,
        stacklevel=2
    )
    until = until if until else datetime.now(timezone.utc)
    since = _dt_or_default(since, default_days=365)

    items = _fetch_from_cryptopanic(since, until)
    if not items:
        items = _fetch_from_newsapi(since, until)
    if not items:
        items = _fetch_mock(since, until)
    return items


def save_attention_data(news_list):
    """已废弃：不再写入 CSV。本函数现在会抛出错误以避免旧存储被使用。"""
    raise RuntimeError(
        "save_attention_data is deprecated and CSV storage is disabled. "
        "Use database write paths via scripts/fetch_news_data.py (db.save_news)."
    )


if __name__ == "__main__":
    news = fetch_zec_news()
    save_attention_data(news)
