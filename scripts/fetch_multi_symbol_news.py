#!/usr/bin/env python3
"""
多币种新闻数据获取脚本
支持批量抓取主流加密货币新闻，自动标记币种关联
"""
import os
import sys
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Set
import logging
from dotenv import load_dotenv
import time

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import RAW_DATA_DIR
from src.data.db_storage import get_db, USE_DATABASE
from src.features.news_features import source_weight, sentiment_score, extract_tags

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 主流币种列表（可扩展）
SUPPORTED_SYMBOLS = [
    "BTC", "ETH", "ZEC", "XMR",  # 隐私币 + 主流
    "SOL", "ADA", "DOGE", "XRP",  # 其他主流
]

# 币种别名映射（用于文本匹配）
SYMBOL_ALIASES = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth", "ether"],
    "ZEC": ["zcash", "zec"],
    "XMR": ["monero", "xmr"],
    "SOL": ["solana", "sol"],
    "ADA": ["cardano", "ada"],
    "DOGE": ["dogecoin", "doge"],
    "XRP": ["ripple", "xrp"],
}


def detect_symbols_in_text(text: str) -> Set[str]:
    """从文本中检测提及的币种"""
    text_lower = text.lower()
    detected = set()
    
    for symbol, aliases in SYMBOL_ALIASES.items():
        if any(alias in text_lower for alias in aliases):
            detected.add(symbol)
    
    return detected


def fetch_cryptocompare_multi_symbol(days: int = 90, max_articles: int = 5000) -> List[Dict]:
    """
    CryptoCompare 通用新闻 API（不限币种，全量抓取后过滤）
    扩展到 90 天历史
    """
    url = "https://min-api.cryptocompare.com/data/v2/news/"
    
    news_list = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ts = int(cutoff.timestamp())
    
    last_ts = None
    max_pages = 200  # 增加页数以覆盖更长时间
    page_count = 0
    
    try:
        logger.info(f"[CryptoCompare] Fetching news for last {days} days (all symbols)...")
        
        while page_count < max_pages and len(news_list) < max_articles:
            params = {"lang": "EN"}
            if last_ts:
                params["lTs"] = last_ts
            
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
                if published_ts == 0:
                    continue
                
                if oldest_in_page is None or published_ts < oldest_in_page:
                    oldest_in_page = published_ts
                
                if published_ts < cutoff_ts:
                    reached_cutoff = True
                    continue
                
                dt = datetime.fromtimestamp(published_ts, tz=timezone.utc)
                
                # 检测文章中提及的币种
                title = article.get("title", "")
                body = article.get("body", "")
                combined_text = title + " " + body
                
                detected_symbols = detect_symbols_in_text(combined_text)
                
                # 跳过无关文章
                if not detected_symbols:
                    continue
                
                # 判断相关性：标题提及为 direct，仅正文提及为 related
                title_symbols = detect_symbols_in_text(title)
                if title_symbols:
                    relevance = "direct"
                else:
                    relevance = "related"
                
                news_list.append({
                    "timestamp": int(dt.timestamp() * 1000),
                    "datetime": dt.isoformat(),
                    "title": title,
                    "source": article.get("source", "CryptoCompare"),
                    "url": article.get("url", article.get("guid", "")),
                    "symbols": ",".join(sorted(detected_symbols)),  # 多币种关联
                    "relevance": relevance,
                })
            
            if reached_cutoff:
                logger.info(f"[CryptoCompare] Reached cutoff date, page {page_count + 1}")
                break
            
            if oldest_in_page:
                last_ts = oldest_in_page - 1
                page_count += 1
                
                # 速率限制
                time.sleep(0.2)
            else:
                break
            
            if page_count % 10 == 0:
                logger.info(f"[CryptoCompare] Page {page_count}: {len(news_list)} relevant articles so far")
        
        logger.info(f"[CryptoCompare] Fetched {len(news_list)} articles across {page_count + 1} pages")
        
    except Exception as e:
        logger.error(f"[CryptoCompare] Error: {e}")
    
    return news_list


def fetch_cryptopanic_multi_symbol(symbols: List[str], days: int = 90) -> List[Dict]:
    """
    CryptoPanic API 多币种批量抓取
    """
    token = os.getenv("CRYPTOPANIC_API_KEY") or os.getenv("CRYPTOPANIC_TOKEN")
    if not token:
        logger.warning("[CryptoPanic] No API token, skipping")
        return []
    
    url = "https://cryptopanic.com/api/v1/posts/"
    news_list = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    for symbol in symbols:
        logger.info(f"[CryptoPanic] Fetching {symbol} news...")
        
        next_cursor = None
        max_pages = 20
        page_count = 0
        
        try:
            while page_count < max_pages:
                params = {
                    "auth_token": token,
                    "currencies": symbol,
                    "kind": "news",
                    "public": "true",
                }
                
                if next_cursor:
                    params["cursor"] = next_cursor
                
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                if not results:
                    break
                
                for item in results:
                    created = item.get("published_at") or item.get("created_at")
                    if not created:
                        continue
                    
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    
                    if dt < cutoff:
                        break
                    
                    # 币种关联
                    currencies = item.get("currencies", [])
                    if currencies:
                        detected = {c.get("code") for c in currencies if c.get("code")}
                    else:
                        detected = {symbol}
                    
                    news_list.append({
                        "timestamp": int(dt.timestamp() * 1000),
                        "datetime": dt.isoformat(),
                        "title": item.get("title", ""),
                        "source": item.get("source", {}).get("title", "CryptoPanic"),
                        "url": item.get("url", ""),
                        "symbols": ",".join(sorted(detected)),
                        "relevance": "direct",
                    })
                
                # 分页
                next_cursor = data.get("next")
                if not next_cursor:
                    break
                
                page_count += 1
                time.sleep(0.5)  # 速率限制
            
            logger.info(f"[CryptoPanic] {symbol}: {len([n for n in news_list if symbol in n['symbols']])} articles")
            
        except Exception as e:
            logger.error(f"[CryptoPanic] {symbol} error: {e}")
    
    return news_list


def deduplicate_news(news_list: List[Dict]) -> List[Dict]:
    """去重（基于 URL）"""
    seen_urls = set()
    unique_news = []
    
    for item in news_list:
        url = item.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_news.append(item)
    
    return unique_news


def enrich_news_features(news_list: List[Dict]) -> List[Dict]:
    """为新闻添加特征字段"""
    for item in news_list:
        title = item.get("title", "")
        source = item.get("source", "Unknown")
        
        # 计算特征
        if "source_weight" not in item:
            item["source_weight"] = source_weight(source)
        if "sentiment_score" not in item:
            item["sentiment_score"] = sentiment_score(title)
        if "tags" not in item:
            item["tags"] = ",".join(extract_tags(title))
    
    return news_list


def save_to_database(news_list: List[Dict]):
    """保存到数据库"""
    if not USE_DATABASE:
        logger.warning("Database mode disabled, skipping DB save")
        return
    
    try:
        db = get_db()
        db.save_news(news_list)
        logger.info(f"Saved {len(news_list)} news items to database")
    except Exception as e:
        logger.error(f"Failed to save to database: {e}")


def save_to_csv_backup(news_list: List[Dict], filename: str = "all_crypto_news.csv"):
    """CSV 备份（所有币种混合）"""
    df = pd.DataFrame(news_list)
    if df.empty:
        logger.warning("No news to save to CSV")
        return
    
    # 按时间排序
    df = df.sort_values("datetime", ascending=False)
    
    output_path = RAW_DATA_DIR / filename
    df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} news items to {output_path}")


def main():
    """主流程"""
    logger.info("Starting multi-symbol news fetch...")
    
    all_news = []
    
    # 1. CryptoCompare 通用抓取（全量，90天）
    cc_news = fetch_cryptocompare_multi_symbol(days=90, max_articles=5000)
    all_news.extend(cc_news)
    
    # 2. CryptoPanic 分币种抓取（补充）
    cp_news = fetch_cryptopanic_multi_symbol(SUPPORTED_SYMBOLS, days=90)
    all_news.extend(cp_news)
    
    # 3. 去重
    all_news = deduplicate_news(all_news)
    logger.info(f"After deduplication: {len(all_news)} unique articles")
    
    # 4. 特征增强
    all_news = enrich_news_features(all_news)
    
    # 5. 保存到数据库（仅数据库模式，不生成CSV）
    save_to_database(all_news)
    
    # 统计
    logger.info("\n=== Statistics ===")
    df = pd.DataFrame(all_news)
    if not df.empty:
        logger.info(f"Date range: {df['datetime'].min()} to {df['datetime'].max()}")
        logger.info(f"Total articles: {len(df)}")
        
        # 按币种统计
        symbol_counts = {}
        for symbols_str in df['symbols']:
            for sym in str(symbols_str).split(','):
                sym = sym.strip()
                if sym:
                    symbol_counts[sym] = symbol_counts.get(sym, 0) + 1
        
        logger.info("Articles per symbol:")
        for sym, count in sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {sym}: {count}")
    
    logger.info("Fetch completed!")


if __name__ == "__main__":
    main()
