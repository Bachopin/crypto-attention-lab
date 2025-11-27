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
from src.data.db_storage import get_db, USE_DATABASE
from src.config.settings import TRACKED_SYMBOLS
from src.features.news_features import source_weight, sentiment_score, relevance_flag, extract_tags

# 加载 .env 文件
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_cryptocompare_news(days: int = 90) -> List[Dict]:
    """
    CryptoCompare News API - 免费，无需 API key
    使用分页方式获取历史新闻
    为了确保各币种都有足够的历史数据，我们将分别针对每个币种进行抓取
    """
    url = "https://min-api.cryptocompare.com/data/v2/news/"
    news_list = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ts = int(cutoff.timestamp())
    
    # 定义要抓取的类别/币种
    categories = ["ZEC", "BTC", "ETH", "SOL"]
    
    for category in categories:
        logger.info(f"[CryptoCompare] Fetching news for category: {category}...")
        last_ts = None
        max_pages = 50  # 每个币种抓取 50 页
        page_count = 0
        
        while page_count < max_pages:
            params = {
                "lang": "EN",
                "categories": category
            }
            
            if last_ts:
                params["lTs"] = last_ts
            
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                articles = data.get("Data", [])
                if not articles:
                    break
                
                oldest_in_page = None
                reached_cutoff = False
                
                for article in articles:
                    published_ts = article.get("published_on", 0)
                    if published_ts == 0: continue
                    
                    if oldest_in_page is None or published_ts < oldest_in_page:
                        oldest_in_page = published_ts
                    
                    if published_ts < cutoff_ts:
                        reached_cutoff = True
                        continue
                    
                    dt = datetime.fromtimestamp(published_ts, tz=timezone.utc)
                    
                    news_list.append({
                        "timestamp": int(dt.timestamp() * 1000),
                        "datetime": dt.isoformat(),
                        "title": article.get("title", ""),
                        "source": article.get("source", "CryptoCompare"),
                        "url": article.get("url", article.get("guid", "")),
                        "relevance": "direct",
                    })
                
                if reached_cutoff:
                    logger.info(f"[CryptoCompare] [{category}] Reached cutoff date")
                    break
                
                if oldest_in_page:
                    last_ts = oldest_in_page - 1
                    page_count += 1
                else:
                    break
                    
            except Exception as e:
                logger.error(f"[CryptoCompare] Failed for {category}: {e}")
                break
                
    logger.info(f"[CryptoCompare] Total fetched {len(news_list)} articles")
    return news_list


def fetch_cryptopanic_news(days: int = 14) -> List[Dict]:
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
    max_pages = 50  # 增加最大页数
    page_count = 0
    
    try:
        logger.info(f"[CryptoPanic] Fetching news for last {days} days...")
        
        while page_count < max_pages:
            params = {
                "auth_token": token,
                # "currencies": "ZEC", # 获取所有新闻
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
    为了绕过单次请求 100 条的限制，我们将时间段切分为多个小块（每 5 天一块）
    """
    api_key = os.getenv("NEWS_API_KEY") or os.getenv("NEWSAPI_KEY")
    if not api_key:
        logger.warning("[NewsAPI] No API key found, skipping")
        return []
    
    # 免费版最多 30 天
    days = min(days, 30)
    url = "https://newsapi.org/v2/everything"
    
    news_list = []
    
    # 将时间段切分为 5 天的块，倒序请求
    chunk_size = 5
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    current_end = end_date
    
    try:
        logger.info(f"[NewsAPI] Fetching news (last {days} days) in chunks...")
        
        while current_end > start_date:
            current_start = max(current_end - timedelta(days=chunk_size), start_date)
            
            params = {
                "q": "(crypto OR bitcoin OR ethereum OR blockchain OR Zcash OR ZEC OR Solana OR SOL)",
                "language": "en",
                "sortBy": "publishedAt",
                "from": current_start.isoformat(),
                "to": current_end.isoformat(),
                "pageSize": 100,
                "apiKey": api_key,
            }
            
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                articles = data.get("articles", [])
                logger.info(f"[NewsAPI] {current_start.date()} to {current_end.date()}: {len(articles)} articles")
                
                for article in articles:
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
            except Exception as chunk_err:
                logger.warning(f"[NewsAPI] Chunk failed: {chunk_err}")
            
            # 移动到下一个时间块
            current_end = current_start
            
        logger.info(f"[NewsAPI] Total fetched {len(news_list)} articles")
        
    except Exception as e:
        logger.error(f"[NewsAPI] Failed: {e}")
    
    return news_list


def fetch_rss_feeds() -> List[Dict]:
    """
    RSS 聚合 - 免费无限制，作为补充数据源
    """
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cryptoslate.com/feed/",
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
        "https://bitcoinmagazine.com/.rss/full/",
        "https://news.bitcoin.com/feed",
        "https://thedefiant.io/api/feed",
        "https://blockworks.co/feed",
        # 新增源
        "https://u.today/rss.php",
        "https://www.newsbtc.com/feed/",
        "https://beincrypto.com/feed/",
        "https://dailyhodl.com/feed/",
        "https://coingape.com/feed/",
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
                
                # 不再过滤 ZEC/Zcash 相关，获取所有
                # if not any(kw.lower() in title.lower() for kw in ["zec", "zcash", "privacy coin"]):
                #     continue
                
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
                    "relevance": "direct" # 默认相关
                })
            
            # logger.info(f"[RSS] {source}: {len([n for n in news_list if source in n['source']])} relevant articles")
            
        except Exception as e:
            logger.error(f"[RSS] Failed to fetch {feed_url}: {e}")
    
    logger.info(f"[RSS] Total fetched {len(news_list)} relevant articles")
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


def detect_symbols(text: str) -> str:
    """检测文本中包含的关注币种"""
    found = []
    text_lower = text.lower()
    for sym_pair in TRACKED_SYMBOLS:
        # TRACKED_SYMBOLS 格式如 "ZEC/USDT"
        base = sym_pair.split('/')[0]
        if base.lower() in text_lower:
            found.append(base)
    return ','.join(found) if found else ''

def save_news_data(df: pd.DataFrame):
    """保存到本地和数据库"""
    if df.empty:
        logger.warning("No news to save!")
        return
    
    # 计算新闻特征
    df['source_weight'] = df['source'].apply(lambda s: source_weight(str(s)))
    df['sentiment_score'] = df['title'].apply(lambda t: sentiment_score(str(t)))
    if 'relevance' not in df.columns:
        df['relevance'] = 'direct'
    df['tags'] = df['title'].apply(lambda t: ','.join(extract_tags(str(t))))
    
    # 自动检测相关币种
    df['symbols'] = df.apply(lambda row: detect_symbols(str(row['title']) + " " + str(row.get('body', ''))), axis=1)
    
    # 保存到数据库（主存储）
    if USE_DATABASE:
        try:
            db = get_db()
            records = df.to_dict('records')
            db.save_news(records)
            logger.info(f"✅ Saved {len(records)} news items to database")
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
            # 数据库失败时才回退到 CSV
            filepath = DATA_DIR / "attention_zec_news.csv"
            df.to_csv(filepath, index=False)
            logger.warning(f"⚠️ Fallback: Saved to {filepath.name}")
    
    # 统计
    latest = pd.to_datetime(df["datetime"]).max()
    oldest = pd.to_datetime(df["datetime"]).min()
    logger.info(f"Date range: {oldest.date()} to {latest.date()}")
    logger.info(f"Sources: {df['source'].value_counts().to_dict()}")


def run_news_fetch_pipeline(days: int = 1):
    """
    运行完整的新闻获取流程（供外部调用）
    默认只获取最近 1 天的数据，用于定期更新
    """
    logger.info("="*60)
    logger.info(f"Starting scheduled news aggregation (last {days} days)...")
    logger.info("="*60)
    
    all_news = []
    
    # 1. CryptoCompare
    try:
        all_news.extend(fetch_cryptocompare_news(days=days))
    except Exception as e:
        logger.error(f"CryptoCompare failed: {e}")
        
    # 2. CryptoPanic
    try:
        all_news.extend(fetch_cryptopanic_news(days=days))
    except Exception as e:
        logger.error(f"CryptoPanic failed: {e}")
        
    # 3. NewsAPI (API 限制较多，定期更新时可以跳过或减少频率，这里保留但只查最近)
    try:
        all_news.extend(fetch_newsapi_news(days=min(days, 30)))
    except Exception as e:
        logger.error(f"NewsAPI failed: {e}")
        
    # 4. RSS (始终运行)
    try:
        logger.info("[RSS] Fetching RSS feeds...")
        all_news.extend(fetch_rss_feeds())
    except Exception as e:
        logger.error(f"RSS failed: {e}")
    
    # 去重并保存
    if all_news:
        df = aggregate_and_deduplicate(all_news)
        save_news_data(df)
        logger.info(f"Scheduled update completed: {len(df)} items processed")
    else:
        logger.info("Scheduled update completed: No news found")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch crypto news data")
    parser.add_argument("--days", type=int, default=90, help="Number of days to look back")
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info(f"Starting multi-source news aggregation for ZEC/Zcash (last {args.days} days)...")
    logger.info("="*60)
    
    all_news = []
    
    # 优先级 1: CryptoCompare (免费，无 key)
    all_news.extend(fetch_cryptocompare_news(days=args.days))
    
    # 优先级 2: CryptoPanic (需要 token)
    all_news.extend(fetch_cryptopanic_news(days=args.days))
    
    # 优先级 3: NewsAPI (免费版最多 30 天)
    all_news.extend(fetch_newsapi_news(days=min(args.days, 30)))
    
    # 优先级 4: RSS 聚合 (始终运行，作为补充)
    logger.info("[RSS] Fetching RSS feeds...")
    all_news.extend(fetch_rss_feeds())
    
    # 去重并保存
    df = aggregate_and_deduplicate(all_news)
    save_news_data(df)
    
    logger.info("\n" + "="*60)
    logger.info("News aggregation completed!")
