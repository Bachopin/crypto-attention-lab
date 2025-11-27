#!/usr/bin/env python3
"""
清理价格表中重复的记录，并为 (symbol_id, timeframe, datetime) 建立唯一索引。

判定重复：同一 (symbol_id, timeframe, datetime) 出现多条记录。
保留规则：保留最小 id（最早写入），删除其它记录。

此外，会确保存在唯一索引以防止后续重复写入。
"""
from __future__ import annotations

from sqlalchemy import text
from src.database.models import get_engine


def main() -> None:
    engine = get_engine()  # 主库（包含 prices）
    with engine.begin() as conn:
        # 1) 删除重复记录，保留每组的最小 id
        # 适用于 SQLite/Postgres 的通用写法（使用子查询）
        # 先找出需要删除的 id 列表
        find_dups_sql = text(
            """
            SELECT p.id
            FROM prices p
            JOIN (
                SELECT symbol_id, timeframe, datetime, MIN(id) AS keep_id, COUNT(*) AS cnt
                FROM prices
                GROUP BY symbol_id, timeframe, datetime
                HAVING COUNT(*) > 1
            ) g
            ON p.symbol_id = g.symbol_id AND p.timeframe = g.timeframe AND p.datetime = g.datetime
            WHERE p.id <> g.keep_id
            """
        )

        dups = [row[0] for row in conn.execute(find_dups_sql).fetchall()]
        if dups:
            print(f"🔎 检测到重复价格记录 {len(dups)} 条，正在删除...")
            # 分批删除避免 SQL 过长
            batch = 1000
            for i in range(0, len(dups), batch):
                subset = dups[i:i+batch]
                conn.execute(text("DELETE FROM prices WHERE id IN (%s)" % ",".join(map(str, subset))))
            print("🧹 重复价格记录已清理完毕。")
        else:
            print("✅ 未发现重复价格记录。")

        # 2) 建立唯一索引（如果不存在）
        # 在 SQLite 中，重复创建相同名称的索引会报错，因此使用 IF NOT EXISTS
        conn.execute(text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_price_symbol_tf_dt
            ON prices(symbol_id, timeframe, datetime)
            """
        ))
        print("🔒 已确保唯一索引 uq_price_symbol_tf_dt 存在。")


if __name__ == '__main__':
    main()
