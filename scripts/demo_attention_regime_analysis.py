"""
Demo: 多币种 attention regime 分析
"""
from datetime import datetime
from src.research.attention_regimes import analyze_attention_regimes

if __name__ == "__main__":
    symbols = ["ZEC", "BTC", "ETH"]
    lookahead_days = [7, 30]
    res = analyze_attention_regimes(
        symbols=symbols,
        lookahead_days=lookahead_days,
        attention_source="composite",
        split_method="quantile",
        start=datetime(2023, 1, 1),
        end=datetime(2025, 11, 1),
    )
    for sym in symbols:
        print(f"=== {sym} ===")
        stats = res.get(sym, {}).get("stats", {})
        for regime in ["low", "mid", "high"]:
            r = stats.get(regime)
            if not r:
                continue
            print(f"Regime: {regime}")
            for k in lookahead_days:
                s = r.get(str(k), {})
                print(f"  {k}D: mean={s.get('mean'):.4f}  pos_ratio={s.get('pos_ratio'):.2%}  N={s.get('count')}")
        print()
