#!/usr/bin/env python3
"""
Recompute StateSnapshot records after attention weight updates.

This script rebuilds snapshots for impacted symbols/timeframes using the
latest `attention_features` and price data via MarketDataService, ensuring
features that depend on:
- composite_attention_score / zscore
- news_channel_score
- bullish_attention / bearish_attention
are refreshed accordingly.

It supports dry-run mode to preview counts and sample diffs without DB writes.
"""

import argparse
import sys
import os
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# Ensure repository root is on sys.path when running as a script
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.config.settings import DATABASE_URL
from src.database.models import Symbol, StateSnapshot, AttentionFeature
from src.research.state_snapshot import compute_state_snapshot


def get_active_symbols(session, symbols_filter: Optional[List[str]] = None) -> List[str]:
    q = session.query(Symbol).filter(Symbol.is_active == True)
    if symbols_filter:
        q = q.filter(Symbol.symbol.in_([s.upper() for s in symbols_filter]))
    return [s.symbol for s in q.all()]


def upsert_snapshot(session, symbol_id: int, snapshot: StateSnapshot):
    # Map timeframe to DB format: state_snapshots uses '1d' / '4h'
    tf_db = snapshot.timeframe

    existing = (
        session.query(StateSnapshot)
        .filter(
            StateSnapshot.symbol_id == symbol_id,
            StateSnapshot.datetime == snapshot.as_of,
            StateSnapshot.timeframe == tf_db,
            StateSnapshot.window_days == snapshot.window_days,
        )
        .first()
    )

    if existing:
        existing.features = snapshot.features and __import__('json').dumps(snapshot.features, ensure_ascii=False)
        existing.raw_stats = snapshot.raw_stats and __import__('json').dumps(snapshot.raw_stats, ensure_ascii=False)
    else:
        from src.database.models import StateSnapshot as SnapshotModel
        sm = SnapshotModel.from_computed(
            symbol_id=symbol_id,
            dt=snapshot.as_of,
            timeframe=tf_db,
            features=snapshot.features,
            raw_stats=snapshot.raw_stats,
            window_days=snapshot.window_days,
        )
        session.add(sm)


def main():
    parser = argparse.ArgumentParser(description="Recompute StateSnapshot after attention weight updates")
    parser.add_argument("--symbols", nargs="+", help="Symbols to recompute (space-separated). Omit to update all active.")
    parser.add_argument("--timeframe", default="1d", choices=["1d", "4h"], help="Timeframe (default: 1d)")
    parser.add_argument("--window-days", type=int, default=30, help="Window days (default: 30)")
    parser.add_argument("--as-of", help="ISO datetime for snapshot (UTC). Default: now")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run without DB writes; prints sample diffs")
    parser.add_argument("--full", action="store_true", help="Recompute snapshots for all available datetimes in DB for the given timeframe")

    args = parser.parse_args()

    as_of = None
    if args.as_of:
        try:
            as_of = datetime.fromisoformat(args.as_of)
            if as_of.tzinfo is None:
                as_of = as_of.replace(tzinfo=timezone.utc)
        except Exception:
            print("Invalid --as-of format. Use ISO 8601, e.g. 2025-12-02T00:00:00Z", file=sys.stderr)
            return 1

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        symbols = get_active_symbols(session, args.symbols)
        if not symbols:
            print("No active symbols found.")
            return 0

        print("============================================================")
        print("Recomputing State Snapshots")
        print("============================================================")
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Timeframe: {args.timeframe}, Window: {args.window_days}d")
        print(f"Mode: {'DRY-RUN' if args.dry_run else 'WRITE'}")

        updated = 0
        for sym in symbols:
            sym_row = session.query(Symbol).filter(Symbol.symbol == sym).first()
            if not sym_row:
                print(f"  ⚠️  Missing symbol {sym}, skipping")
                continue

            # Determine datetimes to process
            datetimes = []
            if args.full:
                tf_db = 'D' if args.timeframe == '1d' else '4H'
                rows = (
                    session.query(AttentionFeature.datetime)
                    .filter(AttentionFeature.symbol_id == sym_row.id)
                    .filter(AttentionFeature.timeframe == tf_db)
                    .order_by(AttentionFeature.datetime.asc())
                    .all()
                )
                datetimes = [r[0] for r in rows]
                if not datetimes:
                    print(f"  ⚠️  No attention features for {sym} {args.timeframe}, skipping")
                    continue
            else:
                # Single point (now or provided as_of)
                datetimes = [as_of]

            count = 0
            batch = 0
            for dt in datetimes:
                snap = compute_state_snapshot(
                    symbol=sym,
                    as_of=dt,
                    timeframe=args.timeframe,
                    window_days=args.window_days,
                )
                if not snap:
                    continue

                if args.dry_run:
                    feats = snap.features
                    print(f"\n📌 {sym} snapshot @ {snap.as_of.isoformat()} ({args.timeframe})")
                    print(f"  att_composite_z: {feats.get('att_composite_z', 0):.4f}")
                    print(f"  att_news_z:      {feats.get('att_news_z', 0):.4f}")
                    print(f"  att_trend_7d:    {feats.get('att_trend_7d', 0):.4f}")
                    print(f"  bull_minus_bear: {feats.get('bullish_minus_bearish', 0):.4f}")
                    print(f"  shares (news/google/twitter): {feats.get('att_news_share', 0):.2f} / {feats.get('att_google_share', 0):.2f} / {feats.get('att_twitter_share', 0):.2f}")
                else:
                    upsert_snapshot(session, sym_row.id, snap)
                    updated += 1
                    count += 1
                    batch += 1
                    if batch % 500 == 0:
                        # Periodic commit to avoid huge transactions
                        session.commit()
                        batch = 0

            if not args.dry_run:
                print(f"  ✅ {sym}: updated {count} snapshots ({args.timeframe})")

        if not args.dry_run:
            session.commit()
            print(f"\n✅ Total snapshots updated: {updated}")
        else:
            print("\n🔍 DRY-RUN complete (no DB writes)")

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        session.rollback()
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
