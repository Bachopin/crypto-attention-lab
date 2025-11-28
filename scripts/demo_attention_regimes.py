#!/usr/bin/env python3
"""
Demo script for Attention Regime Analysis.
"""

import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.research.attention_regimes import analyze_attention_regimes

def main():
    print("Running Attention Regime Analysis Demo...")
    
    symbols = ["ZEC", "BTC", "ETH"]
    lookahead_days = [7, 30]
    attention_source = "composite"
    
    # Set a reasonable date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2) # 2 years
    
    print(f"Symbols: {symbols}")
    print(f"Time range: {start_date.date()} to {end_date.date()}")
    print(f"Attention Source: {attention_source}")
    print("-" * 50)
    
    try:
        results = analyze_attention_regimes(
            symbols=symbols,
            lookahead_days=lookahead_days,
            attention_source=attention_source,
            split_method="tercile",
            start=start_date,
            end=end_date
        )
        
        # Print results in a readable format
        for symbol, data in results.items():
            print(f"\n=== {symbol} ===")
            
            if "meta" in data and "error" in data["meta"]:
                print(f"Error: {data['meta']['error']}")
                continue
                
            regimes = data.get("regimes", [])
            if not regimes:
                print("No regimes found.")
                continue
                
            # Print table header
            print(f"{'Regime':<10} {'Range':<20} {'Lookahead':<10} {'Avg Return':<12} {'Win Rate':<10} {'Count':<8}")
            print("-" * 75)
            
            for regime in regimes:
                name = regime["name"]
                q_range = regime["quantile_range"]
                range_str = f"[{q_range[0]:.2f}, {q_range[1]:.2f}]"
                
                stats = regime["stats"]
                for k, stat in stats.items():
                    avg_ret = stat["avg_return"]
                    pos_ratio = stat["pos_ratio"]
                    count = stat["sample_count"]
                    
                    avg_ret_str = f"{avg_ret*100:.2f}%" if avg_ret is not None else "N/A"
                    pos_ratio_str = f"{pos_ratio*100:.1f}%" if pos_ratio is not None else "N/A"
                    
                    print(f"{name:<10} {range_str:<20} {k+'d':<10} {avg_ret_str:<12} {pos_ratio_str:<10} {count:<8}")
                    
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()