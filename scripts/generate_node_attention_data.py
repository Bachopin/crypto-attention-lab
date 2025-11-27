"""批量生成节点级注意力特征数据。

用法：
    python scripts/generate_node_attention_data.py

会遍历当前数据库/CSV 中可用的 symbol 列表，为每个 symbol
计算节点级特征并持久化到数据库或 CSV。
"""

import pandas as pd

from src.data.db_storage import get_available_symbols
from src.features.node_attention_features import build_node_attention_features, save_node_attention_features


def main():
  symbols = get_available_symbols()
  if not symbols:
      print("No symbols found in database/CSV.")
      return

  print("Generating node attention features for symbols:", ", ".join(symbols))

  all_rows = 0
  for sym in symbols:
      try:
          df = build_node_attention_features(symbol=sym, freq="D")
          if df.empty:
              print(f"[skip] {sym}: no node-level news data.")
              continue
          save_node_attention_features(df)
          all_rows += len(df)
          print(f"[ok] {sym}: saved {len(df)} node attention rows.")
      except Exception as e:
          print(f"[error] {sym}: {e}")

  print(f"Done. Total node attention rows processed: {all_rows}")


if __name__ == "__main__":
  main()
