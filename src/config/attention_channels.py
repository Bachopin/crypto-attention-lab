"""Configuration for multi-channel attention inputs.

This module centralizes the knobs required by the new composite attention stack:
- Source/language level weights for news based channels
- Optional node-factor based adjustment parameters
- Symbol specific keyword/query definitions for Google Trends and Twitter
- Composite score blending coefficients

Keeping everything here allows research iterations without sprinkling magic
numbers across feature modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# -----------------------------
# News channel weighting config
# -----------------------------

LANGUAGE_WEIGHTS: Dict[str, float] = {
    "en": 1.0,
    "zh": 1.0,
    "es": 0.7,
    "ko": 0.75,
    "jp": 0.75,
    "fr": 0.65,
    "de": 0.65,
    "other": 0.6,
}

SOURCE_BASE_WEIGHTS: Dict[str, float] = {
    # English tier (顶级新闻源)
    "CoinDesk": 1.0,
    "coindesk": 1.0,
    "Cointelegraph": 0.95,
    "cointelegraph": 0.95,
    "The Block": 0.92,
    "Decrypt": 0.88,
    "Bloomberg Crypto": 0.85,
    "BeInCrypto": 0.85,
    "NewsAPI": 0.80,
    
    # Chinese tier (中文顶级新闻源 - 权重与英文相当)
    "PANews": 1.0,           # 主要中文源，权重等同 CoinDesk
    "PANews News": 1.0,
    "金色财经": 0.95,         # 权重等同 Cointelegraph
    "Odaily": 0.92,          # 权重等同 The Block
    "星球日报": 0.92,
    "巴比特": 0.88,           # 权重等同 Decrypt
    "链捕手": 0.85,           # 权重等同 BeInCrypto
    
    # English mid-tier (中级英文源)
    "cryptopolitan": 0.75,
    "bitcoinist": 0.75,
    "newsbtc": 0.75,
    "bitcoin.com": 0.75,
    "ambcrypto": 0.72,
    "cryptonews": 0.72,
    "cryptopotato": 0.70,
    "coinotag": 0.70,
    "bitcoinworld": 0.68,
    "thecryptobasic": 0.68,
    "utoday": 0.65,
    
    # Aggregators / misc
    "CryptoPanic": 0.80,
    "CryptoCompare": 0.70,
    "CryptoSlate": 0.65,
    "Biztoc.com": 0.65,
    "coinpaper": 0.60,
    "RSS": 0.55,
    "Unknown": 0.50,
}

DEFAULT_SOURCE_LANGUAGE: Dict[str, str] = {
    # English sources - Top tier
    "CoinDesk": "en",
    "coindesk": "en",
    "Cointelegraph": "en",
    "cointelegraph": "en",
    "Cointelegraph.com News": "en",
    "The Block": "en",
    "Decrypt": "en",
    "decrypt": "en",
    "BeInCrypto": "en",
    "NewsAPI": "en",
    
    # English sources - Mid tier
    "cryptopolitan": "en",
    "bitcoinist": "en",
    "Bitcoinist": "en",
    "newsbtc": "en",
    "NewsBTC": "en",
    "newsBTC": "en",
    "bitcoin.com": "en",
    "Bitcoin News": "en",
    "Bitcoin Magazine": "en",
    "ambcrypto": "en",
    "Ambcrypto.com": "en",
    "cryptonews": "en",
    "Cryptonews": "en",
    "cryptopotato": "en",
    "coinotag": "en",
    "bitcoinworld": "en",
    "thecryptobasic": "en",
    "utoday": "en",
    
    # Aggregators & Platforms
    "Biztoc.com": "en",
    "coinpaper": "en",
    "CryptoSlate": "en",
    "CryptoPanic": "en",
    "CryptoCompare": "en",
    "Crypto Briefing": "en",
    "ZyCrypto": "en",
    "zycrypto": "en",
    
    # Social & Forums
    "bitcoinsistemi": "en",
    "bitdegree": "en",
    "bitzo": "en",
    "blockworks": "en",
    "Blockworks: News and insights about digital assets.": "en",
    "coinpaprika": "en",
    "coinquora": "en",
    "cointurken": "en",
    "cryptocoinnews": "en",
    "cryptocompare": "en",
    "cryptodaily": "en",
    "cryptointelligence": "en",
    "cryptonewsz": "en",
    "Cryptocynews.com": "en",
    "ethereumfoundation": "en",
    "finbold": "en",
    "forbes": "en",
    "Forbes": "en",
    "huobi": "en",
    "invezz": "en",
    "krakenblog": "en",
    "bitfinexblog": "en",
    "seekingalpha": "en",
    "themerkle": "en",
    "timestabloid": "en",
    "trustnodes": "en",
    
    # Media & Press
    "bloomberg_crypto_": "en",
    "Bloomberg Crypto": "en",
    "Bloomberg": "en",
    "financialtimes_crypto_": "en",
    "The Wall Street Journal": "en",
    "TheStreet": "en",
    "investing_comcryptonews": "en",
    "investing_comcryptoopinionandanalysis": "en",
    "Coinjournal.net": "en",
    "Coinspeaker": "en",
    "Coingape": "en",
    "GlobeNewswire": "en",
    "PR Newswire UK": "en",
    "Dlnews.com": "en",
    "pymnts.com": "en",
    "Thefly.com": "en",
    "Paymentsdive.com": "en",
    "Finextra": "en",
    
    # Misc English
    "U.Today - IT, AI and Fintech Daily News for You Today": "en",
    "The Daily Hodl": "en",
    "The Defiant": "en",
    "Slashdot.org": "en",
    "TechRadar": "en",
    "Yahoo Entertainment": "en",
    "Wolfram.com": "en",
    "Pypi.org": "en",
    
    # Chinese sources
    "PANews": "zh",
    "PANews News": "zh",
    "Odaily": "zh",
    "金色财经": "zh",
    "巴比特": "zh",
    "链捕手": "zh",
    "星球日报": "zh",
    "Cointelegraph中文": "zh",
    "Telegram: 区块律动 BlockBeats": "zh",
    "Telegram: Foresight News": "zh",
    "Telegram: 链捕手": "zh",
    "区块律动": "zh",
    "Foresight News": "zh",
    "深潮 TechFlow": "zh",
    "吴说区块链": "zh",
}

# Optional node-factor adjustments (platform level)
ENABLE_NODE_WEIGHT_ADJUSTMENT: bool = True
NODE_ADJUSTMENT_MIN_EVENTS: int = 5
NODE_ADJUSTMENT_LOOKBACK_DAYS: int = 365
NODE_ADJUSTMENT_LOOKAHEAD: str = "1d"
NODE_ADJUSTMENT_SCALING: float = 0.2  # +/-20% multiplier band


# -----------------------------
# Symbol level keyword mappings
# -----------------------------

@dataclass(frozen=True)
class SymbolAttentionConfig:
    google_trends_keywords: List[str]
    twitter_query: str
    default_language: str = "en"
    google_geo: str = "GLOBAL"


SYMBOL_ATTENTION_CONFIG: Dict[str, SymbolAttentionConfig] = {
    "ZEC": SymbolAttentionConfig(
        google_trends_keywords=["Zcash", "ZEC", "Zcash crypto"],
        twitter_query="$ZEC OR Zcash",
        default_language="en",
    ),
    "BTC": SymbolAttentionConfig(
        google_trends_keywords=["Bitcoin", "BTC"],
        twitter_query="$BTC OR Bitcoin",
        default_language="en",
    ),
    "ETH": SymbolAttentionConfig(
        google_trends_keywords=["Ethereum", "ETH"],
        twitter_query="$ETH OR Ethereum",
        default_language="en",
    ),
    "SOL": SymbolAttentionConfig(
        google_trends_keywords=["Solana", "SOL"],
        twitter_query="$SOL OR Solana",
        default_language="en",
    ),
}

DEFAULT_GOOGLE_FREQUENCY = "D"
DEFAULT_TWITTER_GRANULARITY = "day"


# -----------------------------
# Composite attention weighting
# -----------------------------

COMPOSITE_ATTENTION_WEIGHTS: Dict[str, float] = {
    "news": 0.5,
    "google_trends": 0.3,
    "twitter": 0.2,
}

COMPOSITE_SPIKE_QUANTILE: float = 0.9


def get_language_weight(language: Optional[str]) -> float:
    lang = (language or "other").lower()
    return LANGUAGE_WEIGHTS.get(lang, LANGUAGE_WEIGHTS["other"])


def get_source_base_weight(source: Optional[str]) -> float:
    if not source:
        return SOURCE_BASE_WEIGHTS["Unknown"]
    return SOURCE_BASE_WEIGHTS.get(source, SOURCE_BASE_WEIGHTS.get("Unknown", 0.5))


def get_symbol_attention_config(symbol: str) -> SymbolAttentionConfig:
    """
    获取符号的注意力配置，优先使用预定义配置，否则从数据库获取别名
    """
    symbol_up = (symbol or "").upper()
    
    # 优先使用预定义配置
    if symbol_up in SYMBOL_ATTENTION_CONFIG:
        return SYMBOL_ATTENTION_CONFIG[symbol_up]
    
    # 尝试从数据库获取别名作为关键词
    keywords = [symbol_up]  # 默认至少包含符号本身
    
    try:
        from src.data.db_storage import get_symbol_name_map
        mapping = get_symbol_name_map(symbols_filter=[symbol_up])
        if symbol_up in mapping:
            aliases = mapping[symbol_up]
            # 添加代币全称和别名作为关键词
            for alias in aliases:
                if alias and len(alias) > 1:
                    # 过滤太短或太长的别名
                    if 2 <= len(alias) <= 50:
                        keywords.append(alias)
            # 去重并限制数量（Google Trends API 限制 5 个关键词）
            keywords = list(dict.fromkeys(keywords))[:5]
    except Exception:
        pass  # 数据库不可用时使用默认值
    
    return SymbolAttentionConfig(
        google_trends_keywords=keywords,
        twitter_query=f"${symbol_up} OR {' OR '.join(keywords[:3])}",
    )
