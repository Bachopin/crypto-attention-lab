import sys
import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.backtest.attention_rotation import run_attention_rotation_backtest

def main():
    # Define symbols
    symbols = ["ZECUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    # Define date range (last 180 days)
    end_dt = pd.Timestamp.now(tz="UTC")
    start_dt = end_dt - pd.Timedelta(days=180)
    
    print(f"Running Attention Rotation Backtest for: {symbols}")
    print(f"Period: {start_dt} to {end_dt}")
    
    # Run backtest
    result = run_attention_rotation_backtest(
        symbols=symbols,
        attention_source="composite",
        rebalance_days=7,
        lookback_days=30,
        top_k=2,
        start=start_dt,
        end=end_dt
    )
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return

    # Print Summary
    summary = result["summary"]
    print("\n=== Backtest Summary ===")
    for k, v in summary.items():
        print(f"{k}: {v}")
        
    # Print Rebalance Log (First 5)
    print("\n=== Rebalance Log (First 5) ===")
    for log in result["rebalance_log"][:5]:
        print(f"Date: {log['rebalance_date']}")
        print(f"Selected: {log['selected_symbols']}")
        print(f"Scores: {log['attention_values']}")
        print("-" * 20)
        
    # Plot Equity Curve (if matplotlib is available)
    try:
        equity_curve = result["equity_curve"]
        df = pd.DataFrame(equity_curve)
        # Use format='mixed' to handle potential inconsistencies or ISO strings
        df["datetime"] = pd.to_datetime(df["datetime"], format='mixed', utc=True)
        df.set_index("datetime", inplace=True)
        
        plt.figure(figsize=(10, 6))
        plt.plot(df.index, df["equity"], label="Strategy Equity")
        plt.title("Attention Rotation Strategy Equity Curve")
        plt.xlabel("Date")
        plt.ylabel("Equity")
        plt.legend()
        plt.grid(True)
        
        output_path = project_root / "logs" / "attention_rotation_equity.png"
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path)
        print(f"\nEquity curve saved to {output_path}")
    except Exception as e:
        print(f"\nCould not plot equity curve: {e}")

if __name__ == "__main__":
    main()
