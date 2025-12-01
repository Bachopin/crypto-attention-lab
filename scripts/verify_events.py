import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from src.data.db_storage import load_attention_data

def verify_symbol(symbol):
    print(f"--- Verifying {symbol} ---")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    df = load_attention_data(symbol, start_date, end_date)
    
    if df.empty:
        print(f"❌ No data found for {symbol}")
        return
        
    if 'detected_events' not in df.columns:
        print(f"❌ 'detected_events' column missing for {symbol}")
        return

    # Count non-empty events
    # detected_events is likely a JSON string or list, or None/NaN
    def has_event(x):
        if pd.isna(x) or x == "" or x == "[]" or x is None:
            return 0
        return 1

    event_count = df['detected_events'].apply(has_event).sum()
    total_rows = len(df)
    
    print(f"✅ Data found: {total_rows} rows")
    print(f"📊 Rows with events: {event_count}")
    
    if event_count > 0:
        # Show a sample event
        sample = df[df['detected_events'].apply(has_event) == 1].iloc[0]
        print(f"📝 Sample event date: {sample['datetime']}")
        print(f"📝 Sample event content: {sample['detected_events']}")
    else:
        print("⚠️ No events found in the last 90 days.")

if __name__ == "__main__":
    symbols = ['SOL', 'ETH', 'BNB', 'ZEC']
    for s in symbols:
        verify_symbol(s)
