#!/usr/bin/env python
"""Batch fetch Google Trends data for all tracked symbols.

Usage examples:
    python scripts/fetch_multi_symbol_google_trends.py --days 365
    python scripts/fetch_multi_symbol_google_trends.py --symbols ZEC,BTC --force-refresh

The script reuses the same caching logic as attention feature generation:
- Existing data is read from SQLite (when available) and CSV caches under data/processed
- Missing ranges are fetched via pytrends and stored back into both layers
"""
from __future__ import annotations

import argparse
import logging
from typing import Iterable, List

import pandas as pd

from src.config.settings import TRACKED_SYMBOLS
from src.data.db_storage import get_available_symbols
from src.data.google_trends_fetcher import get_google_trends_series

logger = logging.getLogger("google_trends_batch")


def _normalize_symbol(token: str) -> str:
    cleaned = (token or "").upper().strip()
    if not cleaned:
        return ""
    if "/" in cleaned:
        cleaned = cleaned.split("/")[0]
    if cleaned.endswith("USDT"):
        cleaned = cleaned[:-4]
    return cleaned


def _resolve_symbol_list(explicit: str | None) -> List[str]:
    symbols = set()
    if explicit:
        for item in explicit.split(","):
            norm = _normalize_symbol(item)
            if norm:
                symbols.add(norm)
        return sorted(symbols)

    for entry in TRACKED_SYMBOLS:
        norm = _normalize_symbol(entry)
        if norm:
            symbols.add(norm)

    try:
        for entry in get_available_symbols():
            norm = _normalize_symbol(entry)
            if norm:
                symbols.add(norm)
    except Exception as exc:
        logger.warning("Failed to extend symbol list from DB: %s", exc)

    return sorted(symbols)


def _configure_logging(verbose: bool) -> None:
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def fetch_for_symbol(symbol: str, start: pd.Timestamp, end: pd.Timestamp, force_refresh: bool = False) -> int:
    df = get_google_trends_series(symbol, start, end, force_refresh=force_refresh)
    count = 0 if df.empty else len(df)
    logger.info("%s: synced %s rows spanning %s → %s", symbol, count, start.date(), end.date())
    return count


def main():
    parser = argparse.ArgumentParser(description="Fetch Google Trends data for multiple symbols")
    parser.add_argument("--symbols", help="Comma separated base symbols (defaults to TRACKED_SYMBOLS + DB entries)")
    parser.add_argument("--days", type=int, default=365, help="Lookback window in days (default: 365)")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore caches and force a refetch")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")
    args = parser.parse_args()

    _configure_logging(args.verbose)

    symbols = _resolve_symbol_list(args.symbols)
    if not symbols:
        logger.error("No symbols resolved; aborting")
        return 1

    end = pd.Timestamp.utcnow().normalize()
    start = end - pd.Timedelta(days=max(args.days, 1))

    logger.info("Fetching Google Trends for %d symbols (%s → %s)", len(symbols), start.date(), end.date())

    total_rows = 0
    for symbol in symbols:
        try:
            total_rows += fetch_for_symbol(symbol, start, end, force_refresh=args.force_refresh)
        except Exception as exc:  # pragma: no cover - network heavy
            logger.error("Failed to sync Google Trends for %s: %s", symbol, exc, exc_info=args.verbose)

    logger.info("Done. Total rows touched: %d", total_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
