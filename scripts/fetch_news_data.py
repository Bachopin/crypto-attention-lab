#!/usr/bin/env python3
"""
获取 ZEC/Zcash 新闻数据 - 多源聚合方案
支持的新闻源（优先级从高到低）：
1. CryptoCompare News API (免费，无需 key，推荐)
2. CryptoPanic API (免费层每月 20k 请求)
3. NewsAPI (免费层仅支持最近 30 天)
4. RSS 聚合 (CoinDesk/CryptoSlate 等，作为 fallback)
"""
import os
import sys
import requests
import feedparser
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import logging
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_cryptocompare_news(days: int = 60) -> List[Dict]:
    """
    CryptoCompare News API - 免费，无需 API key
    使用分页方式获取历史新闻：通过 lTs 参数逐步往前翻页
    文档: https://min-api.cryptocompare.com/documentation?key=News&cat=latestNewsArticlesEndpoint
    """
    url = "https://min-api.cryptocompare.com/data/v2/news/"
    
    news_list = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ts = int(cutoff.timestamp())
    
    # 分页参数
    last_ts = None  # 最新新闻的时间戳
    max_pages = 100  # 最多翻 100 页（确保覆盖 60 天）
    page_count = 0
    empty_page_count = 0  # 连续空页计数
    max_empty_pages = 5  # 连续 5 页没有相关新闻就停止
    
    try:
        logger.info(f"[CryptoCompare] Fetching news for last {days} days...")
        
        while page_count < max_pages:
            params = {
                "lang": "EN",
            }
            
            # 添加分页参数（从指定时间戳往前查）
            if last_ts:
                params["lTs"] = last_ts
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            articles = data.get("Data", [])
            if not articles:
                logger.info(f"[CryptoCompare] No more articles, stopping at page {page_count}")
                break
            
            # 处理本页文章
            page_relevant = 0
            oldest_in_page = None
            reached_cutoff = False
            
            for article in articles:
                published_ts = article.get("published_on", 0)
                if published_ts == 0:
                    continue
                
                # 记录本页最旧的时间戳，用于下次翻页
                if oldest_in_page is None or published_ts < oldest_in_page:
                    oldest_in_page = published_ts
                
                # 如果已经超过时间范围，标记但继续处理本页
                if published_ts < cutoff_ts:
                    reached_cutoff = True
                    continue
                
                dt = datetime.fromtimestamp(published_ts, tz=timezone.utc)
                
                # 过滤标题/正文包含 ZEC/Zcash/privacy 等相关关键词（放宽条件）
                title = article.get("title", "")
                body = article.get("body", "")
                combined_text = (title + " " + body).lower()
                
                # 主要关键词：ZEC/Zcash
                if "zec" in combined_text or "zcash" in combined_text:
                    relevance = "direct"
                # 次要关键词：隐私币相关（只在标题中）
                elif any(kw in title.lower() for kw in ["privacy coin", "private transaction", "shielded"]):
                    relevance = "related"
                else:
                    continue
                
                news_list.append({
                    "timestamp": int(dt.timestamp() * 1000),
                    "datetime": dt.isoformat(),
                    "title": title,
                    "source": article.get("source", "CryptoCompare"),
                    "url": article.get("url", article.get("guid", "")),
                    "relevance": relevance,  # 标记相关性
                })
                page_relevant += 1
            
            # 如果本页有相关文章，重置空页计数
            if page_relevant > 0:
                empty_page_count = 0
                logger.info(f"[CryptoCompare] Page {page_count + 1}: {page_relevant} relevant articles")
            else:
                empty_page_count += 1
                logger.debug(f"[CryptoCompare] Page {page_count + 1}: 0 relevant articles (empty {empty_page_count}/{max_empty_pages})")
            
            # 停止条件
            if reached_cutoff:
                logger.info(f"[CryptoCompare] Reached cutoff date ({cutoff.date()}), stopping at page {page_count + 1}")
                break
            
            if empty_page_count >= max_empty_pages:
                logger.info(f"[CryptoCompare] {max_empty_pages} consecutive empty pages, stopping at page {page_count + 1}")
                break
            
            # 更新翻页时间戳
            if oldest_in_page:
                last_ts = oldest_in_page - 1  # 从最旧的时间戳往前继续查
                page_count += 1
            else:
                break
        
        logger.info(f"[CryptoCompare] Total fetched {len(news_list)} relevant articles across {page_count + 1} pages")
        
    except Exception as e:
        logger.error(f"[CryptoCompare] Failed: {e}")
    
    return news_list


def fetch_cryptopanic_news(days: int = 60) -> List[Dict]:
    """
    CryptoPanic API - 免费层每月 20k 请求
    支持分页获取历史数据
    注册地址: https://cryptopanic.com/developers/api/
    """
    token = os.getenv("CRYPTOPANIC_API_KEY") or os.getenv("CRYPTOPANIC_TOKEN")
    if not token:
        logger.warning("[CryptoPanic] No API token found, skipping")
        return []
    
    url = "https://cryptopanic.com/api/v1/posts/"
    
    news_list = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # 分页参数
    next_cursor = None
    max_pages = 50  # 最多 50 页
    page_count = 0
    
    try:
        logger.info(f"[CryptoPanic] Fetching news for last {days} days...")
        
        while page_count < max_pages:
            params = {
                "auth_token": token,
                "currencies": "ZEC",
                "kind": "news",
                "public": "true",
            }
            
            # 添加分页游标
            if next_cursor:
                params["cursor"] = next_cursor
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            if not results:
                logger.info(f"[CryptoPanic] No more results at page {page_count + 1}")
                break
            
            page_relevant = 0
            oldest_in_page = None
            
            for item in results:
                created = item.get("published_at") or item.get("created_at")
                if not created:
                    continue
                
                dt = pd.to_datetime(created, utc=True).to_pydatetime()
                
                # 记录最旧的时间
                if oldest_in_page is None or dt < oldest_in_page:
                    oldest_in_page = dt
                
                # 超过时间范围则跳过
                if dt < cutoff:
                    continue
                
                news_list.append({
                    "timestamp": int(dt.timestamp() * 1000),
                    "datetime": dt.isoformat(),
                    "title": item.get("title", "").strip(),
                    "source": (item.get("source") or {}).get("title") or "CryptoPanic",
                    "url": item.get("url", ""),
                    "relevance": "direct",
                })
                page_relevant += 1
            
            logger.info(f"[CryptoPanic] Page {page_count + 1}: {page_relevant} articles (oldest: {oldest_in_page.date() if oldest_in_page else 'N/A'})")
            
            # 获取下一页游标
            next_cursor = data.get("next")
            if not next_cursor:
                logger.info(f"[CryptoPanic] No more pages")
                break
            
            # 如果已经到达时间范围外，停止
            if oldest_in_page and oldest_in_page < cutoff:
                logger.info(f"[CryptoPanic] Reached cutoff date ({cutoff.date()})")
                break
            
            page_count += 1
        
        logger.info(f"[CryptoPanic] Total fetched {len(news_list)} articles across {page_count + 1} pages")
        
    except Exception as e:
        logger.error(f"[CryptoPanic] Failed: {e}")
    
    return news_list


def fetch_newsapi_news(days: int = 30) -> List[Dict]:
    """
    NewsAPI - 免费层只支持最近 30 天
    注册地址: https://newsapi.org/
    """
    api_key = os.getenv("NEWS_API_KEY") or os.getenv("NEWSAPI_KEY")
    if not api_key:
        logger.warning("[NewsAPI] No API key found, skipping")
        return []
    
    # 免费版最多 30 天
    days = min(days, 30)
    
    url = "https://newsapi.org/v2/everything"
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    params = {
        "q": "(Zcash OR ZEC)",
        "language": "en",
        "sortBy": "publishedAt",
        "from": since.isoformat(),
        "pageSize": 100,
        "apiKey": api_key,
    }
    
    news_list = []
    try:
        logger.info(f"[NewsAPI] Fetching news (last {days} days)...")
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        for article in data.get("articles", []):
            dt_raw = article.get("publishedAt")
            if not dt_raw:
                continue
            
            dt = pd.to_datetime(dt_raw, utc=True).to_pydatetime()
            
            news_list.append({
                "timestamp": int(dt.timestamp() * 1000),
                "datetime": dt.isoformat(),
                "title": article.get("title", "").strip(),
                "source": (article.get("source") or {}).get("name", "NewsAPI"),
                "url": article.get("url", ""),
            })
        
        logger.info(f"[NewsAPI] Fetched {len(news_list)} articles")
        
    except Exception as e:
        logger.error(f"[NewsAPI] Failed: {e}")
    
    return news_list


def fetch_rss_feeds() -> List[Dict]:
    """
    RSS 聚合 - 作为 fallback，免费无限制
    """
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cryptoslate.com/feed/",
        "https://cointelegraph.com/rss",
    ]
    
    news_list = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=60)
    
    for feed_url in feeds:
        try:
            logger.info(f"[RSS] Fetching {feed_url}...")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:50]:  # 每个源最多 50 条
                title = entry.get("title", "")
                link = entry.get("link", "")
                
                # 过滤 ZEC/Zcash 相关
                if not any(kw.lower() in title.lower() for kw in ["zec", "zcash"]):
                    continue
                
                # 解析时间
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    from time import mktime
                    dt = datetime.fromtimestamp(mktime(published), tz=timezone.utc)
                else:
                    dt = datetime.now(timezone.utc)
                
                if dt < cutoff:
                    continue
                
                source = feed.feed.get("title", feed_url.split("/")[2])
                
                news_list.append({
                    "timestamp": int(dt.timestamp() * 1000),
                    "datetime": dt.isoformat(),
                    "title": title,
                    "source": source,
                    "url": link,
                })
            
            logger.info(f"[RSS] {source}: {len([n for n in news_list if source in n['source']])} relevant articles")
            
        except Exception as e:
            logger.error(f"[RSS] Failed to fetch {feed_url}: {e}")
    
    return news_list


def aggregate_and_deduplicate(all_news: List[Dict]) -> pd.DataFrame:
    """去重并排序"""
    if not all_news:
        logger.warning("No news data collected from any source!")
        return pd.DataFrame()
    
    df = pd.DataFrame(all_news)
    
    # 去重：基于标题相似度（简单版：完全匹配）
    df = df.drop_duplicates(subset=["title"], keep="first")
    
    # 按时间倒序
    df = df.sort_values("timestamp", ascending=False)
    
    return df


def save_news_data(df: pd.DataFrame):
    """保存到本地"""
    if df.empty:
        logger.warning("No news to save!")
        return
    
    filepath = DATA_DIR / "attention_zec_news.csv"
    df.to_csv(filepath, index=False)
    logger.info(f"✅ Saved {len(df)} news items to {filepath.name}")
    
    # 统计
    latest = pd.to_datetime(df["datetime"]).max()
    oldest = pd.to_datetime(df["datetime"]).min()
    logger.info(f"Date range: {oldest.date()} to {latest.date()}")
    logger.info(f"Sources: {df['source'].value_counts().to_dict()}")


if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Starting multi-source news aggregation for ZEC/Zcash...")
    logger.info("="*60)
    
    all_news = []
    
    # 优先级 1: CryptoCompare (免费，无 key)
    all_news.extend(fetch_cryptocompare_news(days=60))
    
    # 优先级 2: CryptoPanic (需要 token)
    all_news.extend(fetch_cryptopanic_news(days=60))
    
    # 优先级 3: NewsAPI (免费版最多 30 天)
    all_news.extend(fetch_newsapi_news(days=30))
    
    # 优先级 4: RSS 聚合 (fallback)
    if len(all_news) < 50:
        logger.info("[Fallback] Using RSS feeds to supplement news...")
        all_news.extend(fetch_rss_feeds())
    
    # 去重并保存
    df = aggregate_and_deduplicate(all_news)
    save_news_data(df)
    
    logger.info("\n" + "="*60)
    logger.info("News aggregation completed!")
