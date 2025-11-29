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
    "zh": 0.85,
    "es": 0.7,
    "ko": 0.75,
    "jp": 0.75,
    "fr": 0.65,
    "de": 0.65,
    "other": 0.6,
}

SOURCE_BASE_WEIGHTS: Dict[str, float] = {
    # English tier
    "CoinDesk": 1.0,
    "Cointelegraph": 0.95,
    "The Block": 0.92,
    "Decrypt": 0.85,
    "Bloomberg Crypto": 0.8,
    "NewsAPI": 0.75,
    # Chinese tier
    "金色财经": 0.85,
    "巴比特": 0.83,
    "链捕手": 0.8,
    "星球日报": 0.78,
    # Aggregators / misc
    "CryptoPanic": 0.8,
    "CryptoCompare": 0.7,
    "CryptoSlate": 0.65,
    "RSS": 0.55,
    "Unknown": 0.5,
}

DEFAULT_SOURCE_LANGUAGE: Dict[str, str] = {
    "CoinDesk": "en",
    "Cointelegraph": "en",
    "The Block": "en",
    "金色财经": "zh",
    "巴比特": "zh",
    "链捕手": "zh",
    "星球日报": "zh",
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
