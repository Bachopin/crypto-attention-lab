#!/usr/bin/env python3
"""
清理新闻数据库中的疑似 mock 数据

判定规则（任选其一即视为可疑）：
- 标题包含 'Sample' 或 'Mock'（大小写不敏感）
- URL 包含 'example.com' 或 '/mock/'（大小写不敏感）
- 来源包含 'MOCK'（大小写不敏感）

使用方法：
- 预览（不删除）：python scripts/clean_mock_news.py --dry-run
- 实际删除：python scripts/clean_mock_news.py
"""
from __future__ import annotations

import argparse
from typing import List
from pathlib import Path
import sys

# 确保项目根目录可被导入
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import or_

from src.database.models import get_engine, get_session, News
from src.config.settings import NEWS_DATABASE_URL


def find_suspicious(session) -> List[News]:
    # 更保守的判定，避免误伤正常标题中的 "mocked" 等
    cond = or_(
        News.url.ilike('%example.com%'),
        News.url.ilike('%/mock/%'),
        News.url.ilike('%/sample/%'),
        News.source.ilike('mock%'),
        News.source.ilike('% mock %'),
    )
    return session.query(News).filter(cond).order_by(News.datetime.desc()).all()


def main(dry_run: bool = False) -> None:
    engine = get_engine(NEWS_DATABASE_URL)
    session = get_session(engine)
    try:
        suspects = find_suspicious(session)
        count = len(suspects)
        if count == 0:
            print('✅ 没有检测到疑似 mock 新闻，数据库干净。')
            return

        print(f'⚠️ 检测到 {count} 条疑似 mock 新闻：')
        for i, n in enumerate(suspects[:10]):
            print(f"  [{i+1}] {n.datetime.date()} | {n.source} | {n.title[:80]}...")
        if count > 10:
            print(f"  ... 以及另外 {count - 10} 条")

        if dry_run:
            print('\n仅预览模式（--dry-run），未进行删除。')
            return

        # 执行删除
        ids = [n.id for n in suspects]
        del_count = session.query(News).filter(News.id.in_(ids)).delete(synchronize_session=False)
        session.commit()
        print(f'🧹 已删除 {del_count} 条疑似 mock 新闻。')

    finally:
        session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='清理新闻数据库中的疑似 mock 数据')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际删除')
    args = parser.parse_args()
    main(dry_run=args.dry_run)
