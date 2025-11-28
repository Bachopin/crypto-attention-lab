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

POSITIVE_WORDS = [
    "surge", "rally", "bullish", "partnership", "upgrade", "record", "soar", "gain",
]
NEGATIVE_WORDS = [
    "hack", "exploit", "breach", "lawsuit", "fall", "drop", "bearish", "plunge",
]


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
    t = title.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    if pos == 0 and neg == 0:
        return 0.0
    return max(-1.0, min(1.0, (pos - neg) / max(1, pos + neg)))


def extract_tags(title: str) -> List[str]:
    tags: List[str] = []
    tl = title.lower()
    for tag, words in KEYWORD_TAGS.items():
        if any(w in tl for w in words):
            tags.append(tag)
    return tags


def relevance_flag(title: str, symbol: str = "ZEC") -> str:
    # very simple: direct if symbol explicitly present, else related
    pattern = re.compile(r"\b" + re.escape(symbol.lower()) + r"\b")
    return "direct" if pattern.search(title.lower() or "") else "related"
