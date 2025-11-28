import sys
import pathlib

# Ensure project root on path
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.research.attention_regimes import analyze_attention_regimes

def main():
    symbols = ["ZEC", "BTC", "ETH"]
    lookahead_days = [30]
    res = analyze_attention_regimes(
        symbols=symbols,
        lookahead_days=lookahead_days,
        attention_source="composite",
        split_method="tercile",
    )

    results = res.get("results", {})
    for sym in symbols:
        print(f"=== {sym} ===")
        r = results.get(sym, {})
        regimes = r.get("regimes", {})
        for regime_name, stats in regimes.items():
            kkey = "lookahead_30d"
            kstats = stats.get(kkey, {})
            avg_ret = kstats.get("avg_return")
            pos_ratio = kstats.get("pos_ratio")
            scount = kstats.get("sample_count", 0)
            if avg_ret is not None and pos_ratio is not None:
                print(f"{regime_name:>5} | avg_return(30d): {avg_ret:.4f} | pos_ratio: {pos_ratio:.2%} | n={scount}")
            else:
                print(f"{regime_name:>5} | insufficient data (n={scount})")

if __name__ == "__main__":
    main()