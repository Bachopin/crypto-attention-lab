from typing import Dict, List
import re

SOURCE_WEIGHTS: Dict[str, float] = {
    "CoinDesk": 1.0,
    "Cointelegraph": 0.9,
    "CryptoPanic": 0.8,
    "CryptoCompare": 0.7,
    "CryptoSlate": 0.6,
    "RSS": 0.5,
    "Unknown": 0.4,
}

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
    return SOURCE_WEIGHTS.get(source, SOURCE_WEIGHTS["Unknown"])


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
