"""示例脚本：计算并查看节点带货能力因子 Top10。

用法：
    python scripts/compute_node_influence_example.py
"""

import pandas as pd

from src.features.node_influence import compute_node_carry_factor, save_node_carry_factors


def main():
    symbol = "ZEC"
    df = compute_node_carry_factor(symbol=symbol, lookahead="1d", lookback_days=180)
    if df.empty:
        print("No node carry factors computed (empty result).")
        return

    # 保存到持久化存储
    save_node_carry_factors(df)

    # 打印 IR 最高的前 10 个节点
    df_sorted = df.sort_values("ir", ascending=False).head(10)
    print("Top 10 node carry factors for", symbol)
    print(df_sorted.to_string(index=False))


if __name__ == "__main__":
    main()
