
import sys
import os
from pathlib import Path
import pandas as pd
from sqlalchemy import text

# Add project root to python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data.db_storage import get_db, get_session
from src.database.models import Price, Symbol

def debug_price_data(symbol_name="ZECUSDT", timeframe="1d"):
    print(f"Checking price data for {symbol_name} {timeframe}...")
    
    session = get_session()
    try:
        # 1. Check Symbol ID
        sym = session.query(Symbol).filter_by(symbol=symbol_name).first()
        if not sym:
            print(f"Symbol {symbol_name} not found in database.")
            return

        print(f"Symbol ID: {sym.id}")

        # 2. Query Price Data Stats
        query = session.query(Price).filter_by(symbol_id=sym.id, timeframe=timeframe)
        count = query.count()
        print(f"Total records: {count}")

        if count == 0:
            return

        # 3. Check for outliers
        min_price = query.order_by(Price.close.asc()).first()
        max_price = query.order_by(Price.close.desc()).first()
        
        print(f"Min Close: {min_price.close} at {min_price.datetime}")
        print(f"Max Close: {max_price.close} at {max_price.datetime}")

        # 4. Check recent data
        recent_data = query.order_by(Price.datetime.desc()).limit(10).all()
        print("\nRecent 10 records:")
        for p in recent_data:
            print(f"{p.datetime}: O={p.open}, H={p.high}, L={p.low}, C={p.close}, V={p.volume}")

        # 5. Check for potential duplicate timestamps or mixed data
        # Check if there are multiple records for the same timestamp (should be unique constraint, but good to check)
        
        # 6. Check if there are any weird timestamps (e.g. future dates far ahead, or very old dates)
        earliest = query.order_by(Price.datetime.asc()).first()
        latest = query.order_by(Price.datetime.desc()).first()
        print(f"\nDate Range: {earliest.datetime} to {latest.datetime}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    debug_price_data("ZEC", "1d")
    print("-" * 30)
    debug_price_data("BTC", "1d")
