import sys
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data.db_storage import get_db, load_price_data

def check_data():
    db = get_db()
    print("Checking ZEC data...")
    
    # Check directly via get_prices
    df = db.get_prices("ZEC", "1d")
    print(f"Direct DB fetch for ZEC: {len(df)} rows")
    if not df.empty:
        print(df.head())
        
    # Check via load_price_data
    df2, fallback = load_price_data("ZECUSDT", "1d")
    print(f"load_price_data for ZECUSDT: {len(df2)} rows, fallback={fallback}")

if __name__ == "__main__":
    check_data()
