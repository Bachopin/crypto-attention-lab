import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import random
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data.db_storage import get_db

def generate_mock_price_and_attention():
    print("Generating mock price and attention data...")
    
    db = get_db()
    
    symbols = ["ZECUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"]
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=365) # 1 year of data
    
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    
    for symbol in symbols:
        print(f"Processing {symbol}...")
        base_symbol = symbol.replace("USDT", "")
        
        # 1. Generate Price (Random Walk)
        price = 100.0
        price_records = []
        
        # 2. Generate Attention Features
        attention_records = []
        
        for dt in dates:
            # Price
            change = np.random.normal(0, 0.02) # 2% daily volatility
            price *= (1 + change)
            
            price_records.append({
                "timestamp": int(dt.timestamp() * 1000),
                "datetime": dt,
                "open": price * (1 - np.random.uniform(0, 0.01)),
                "high": price * (1 + np.random.uniform(0, 0.01)),
                "low": price * (1 - np.random.uniform(0, 0.01)),
                "close": price,
                "volume": np.random.uniform(100000, 1000000)
            })
            
            # Attention
            # Correlate attention with price volatility/trend slightly
            att_score = 50 + (change * 1000) + np.random.normal(0, 10)
            att_score = max(0, min(100, att_score))
            
            attention_records.append({
                "datetime": dt,
                "news_count": int(np.random.uniform(0, 20)),
                "attention_score": att_score,
                "weighted_attention": att_score * np.random.uniform(0.8, 1.2),
                "bullish_attention": att_score * 0.6,
                "bearish_attention": att_score * 0.4,
                "event_intensity": 1 if att_score > 80 else 0,
                "news_channel_score": att_score,
                "google_trend_value": att_score,
                "google_trend_zscore": (att_score - 50) / 10,
                "twitter_volume": att_score * 100,
                "composite_attention_score": att_score, # Important for our backtest
                "composite_attention_zscore": (att_score - 50) / 10,
                "composite_attention_spike_flag": 1 if att_score > 80 else 0
            })
            
        # Save to DB
        db.save_prices(base_symbol, "1d", price_records)
        db.save_attention_features(base_symbol, attention_records)
        
    print("✅ Mock data generation complete.")

if __name__ == "__main__":
    generate_mock_price_and_attention()
