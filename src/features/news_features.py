from __future__ import annotations

from typing import Dict, List, Optional
import re

from src.config.attention_channels import (
    DEFAULT_SOURCE_LANGUAGE,
    get_language_weight,
    get_source_base_weight,
)
from src.features.node_factor_utils import get_source_level_multiplier

KEYWORD_TAGS = {
    "listing": ["listing", "list on", "added to", "listed"],
    "hack": ["hack", "exploit", "breach"],
    "upgrade": ["upgrade", "update", "hard fork", "fork", "release"],
    "partnership": ["partnership", "partner", "collaboration"],
    "regulation": ["regulation", "sec", "lawsuit", "fine"],
}

# 英文正面词
POSITIVE_WORDS_EN = [
    "surge", "rally", "bullish", "partnership", "upgrade", "record", "soar", "gain",
    "breakout", "pump", "moon", "ath", "all-time high", "positive", "growth", "rise",
    "outperform", "strength", "momentum", "buy", "accumulate", "institutional", "adoption",
]

# 英文负面词
NEGATIVE_WORDS_EN = [
    "hack", "exploit", "breach", "lawsuit", "fall", "drop", "bearish", "plunge",
    "crash", "dump", "scam", "rug", "sell", "sell-off", "decline", "fear", "panic",
    "risk", "loss", "down", "weak", "correction", "bear market", "liquidation",
]

# 中文正面词
POSITIVE_WORDS_ZH = [
    "上涨", "涨", "突破", "创新高", "新高", "大涨", "飙升", "暴涨", "看涨", "利好",
    "牛市", "做多", "增持", "买入", "建仓", "抄底", "反弹", "强势", "强劲", "积极",
    "乐观", "看好", "支撑", "企稳", "回升", "增长", "机会", "潜力", "收益", "盈利",
]

# 中文负面词
NEGATIVE_WORDS_ZH = [
    "下跌", "跌", "暴跌", "跳水", "崩盘", "闪崩", "大跌", "重挫", "看跌", "利空",
    "熊市", "做空", "抛售", "卖出", "清仓", "割肉", "回调", "疲软", "承压", "悲观",
    "担忧", "恐慌", "风险", "亏损", "损失", "破位", "套牢", "被套", "爆仓", "清算",
]

# 合并所有关键词
POSITIVE_WORDS = POSITIVE_WORDS_EN + POSITIVE_WORDS_ZH
NEGATIVE_WORDS = NEGATIVE_WORDS_EN + NEGATIVE_WORDS_ZH


def source_weight(source: str) -> float:
    return get_source_base_weight(source)


def effective_source_weight(
    source: str,
    *,
    language: Optional[str] = None,
    node_id: Optional[str] = None,
    node_weight_lookup: Optional[Dict[str, float]] = None,
) -> float:
    """Calculate the full source weight including language + optional node boost."""

    lang = (language or DEFAULT_SOURCE_LANGUAGE.get(source) or "other").lower()
    base = get_source_base_weight(source) * get_language_weight(lang)

    if node_id:
        adj = get_source_level_multiplier(node_id, node_weight_lookup or {})
    else:
        adj = None

    if adj is not None:
        base *= adj

    return float(base)


def sentiment_score(title: str) -> float:
    """
    计算新闻标题的情感分数
    
    支持英文和中文关键词匹配
    返回值范围: -1.0 到 1.0
    - 正值表示看涨/正面情绪
    - 负值表示看跌/负面情绪
    - 0 表示中性
    """
    if not title:
        return 0.0
    
    # 不区分大小写（英文）
    t_lower = title.lower()
    
    # 统计正面和负面词出现次数
    pos = 0
    neg = 0
    
    for word in POSITIVE_WORDS:
        if word.lower() in t_lower:
            pos += 1
    
    for word in NEGATIVE_WORDS:
        if word.lower() in t_lower:
            neg += 1
    
    if pos == 0 and neg == 0:
        return 0.0
    
    # 归一化到 [-1, 1]
    return max(-1.0, min(1.0, (pos - neg) / max(1, pos + neg)))


def extract_tags(title: str) -> List[str]:
    tags: List[str] = []
    tl = title.lower()
    for tag, words in KEYWORD_TAGS.items():
        if any(w in tl for w in words):
            tags.append(tag)
    return tags


def relevance_flag(title: str, symbol: str) -> str:
    """
    判断新闻与标的的相关性
    
    Args:
        title: 新闻标题
        symbol: 标的符号（如 BTC、ETH）
        
    Returns:
        'direct': 标题中明确提到该标的符号（权重 100%）
        'related': 标题中未明确提到（权重 50%）
    
    Examples:
        >>> relevance_flag("BTC突破新高", "BTC")
        'direct'
        >>> relevance_flag("BTCUSDT分析", "BTC")
        'related'  # BTCUSDT 是一个整体
    """
    if not title or not symbol:
        return "related"
    
    title_lower = title.lower()
    symbol_lower = symbol.lower()
    
    # 查找所有出现位置
    for i in range(len(title_lower) - len(symbol_lower) + 1):
        if title_lower[i:i+len(symbol_lower)] == symbol_lower:
            # 检查前面字符
            if i > 0:
                prev_char = title_lower[i-1]
                # 前面是英文字母或数字，跳过（如 "XBTC"）
                if prev_char.isascii() and prev_char.isalnum():
                    continue
            
            # 检查后面字符
            if i + len(symbol_lower) < len(title_lower):
                next_char = title_lower[i+len(symbol_lower)]
                # 后面是英文字母或数字，跳过（如 "BTCUSDT"）
                if next_char.isascii() and next_char.isalnum():
                    continue
            
            # 找到独立的标的符号
            return "direct"
    
    return "related"
