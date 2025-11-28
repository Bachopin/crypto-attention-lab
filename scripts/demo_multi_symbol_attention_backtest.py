#!/usr/bin/env python
"""Quick smoke test for legacy vs. composite attention backtests.

The script runs the basic attention strategy for a handful of symbols using
both attention sources and prints a compact comparison table.
"""
from __future__ import annotations

import argparse
import logging
from typing import Iterable, List

from src.backtest.basic_attention_factor import run_backtest_basic_attention

DEFAULT_SYMBOLS = ["ZECUSDT", "BTCUSDT", "ETHUSDT"]
SUPPORTED_SOURCES = ("legacy", "composite")


logger = logging.getLogger("demo_backtest")


def _format_summary(symbol: str, payload: dict) -> str:
    if not payload or "summary" not in payload:
        return f"{symbol:<10} | error: {payload.get('error', 'missing data')}"
    summary = payload["summary"]
    win_rate = summary.get("win_rate", 0.0)
    cum_ret = summary.get("cumulative_return", 0.0)
    trades = summary.get("total_trades", 0)
    max_dd = summary.get("max_drawdown", 0.0)
    return (
        f"{symbol:<10} | trades={trades:>3} | win={win_rate:5.1f}% | "
        f"cum={cum_ret*100:6.2f}% | maxDD={max_dd*100:5.2f}%"
    )


def run_suite(
    symbols: Iterable[str],
    attention_source: str,
    lookback_days: int,
    attention_quantile: float,
    holding_days: int,
) -> List[str]:
    rows: List[str] = []
    for symbol in symbols:
        res = run_backtest_basic_attention(
            symbol=symbol,
            attention_source=attention_source,
            lookback_days=lookback_days,
            attention_quantile=attention_quantile,
            holding_days=holding_days,
        )
        rows.append(_format_summary(symbol, res))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare legacy vs composite attention backtests")
    parser.add_argument(
        "--symbols",
        help="Comma separated list of trading symbols (default: ZECUSDT,BTCUSDT,ETHUSDT)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=30,
        help="Lookback window for the quantile filter (default: 30)",
    )
    parser.add_argument(
        "--quantile",
        type=float,
        default=0.8,
        help="Attention quantile threshold (default: 0.8)",
    )
    parser.add_argument(
        "--holding",
        type=int,
        default=3,
        help="Holding period in days (default: 3)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    symbols = [s.strip().upper() for s in (args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS) if s.strip()]
    if not symbols:
        logger.error("No symbols provided")
        return 1

    print("Running basic attention backtests for symbols:", ", ".join(symbols))
    print(f"Parameters: lookback={args.lookback}, quantile={args.quantile}, holding={args.holding}")
    print()

    for source in SUPPORTED_SOURCES:
        print(f"=== Attention Source: {source.upper()} ===")
        rows = run_suite(
            symbols,
            attention_source=source,
            lookback_days=args.lookback,
            attention_quantile=args.quantile,
            holding_days=args.holding,
        )
        for row in rows:
            print(row)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
