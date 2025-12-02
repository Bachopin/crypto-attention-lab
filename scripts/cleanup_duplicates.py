#!/usr/bin/env python3
"""
清理数据库中的重复新闻
基于 (标题, 日期) 进行去重，优先保留真实 URL 的记录
"""
import sys
import logging
from pathlib import Path
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.db_storage import get_db
from src.database.models import News, get_session
from sqlalchemy import func, cast, Date

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_duplicates(dry_run: bool = False):
    db = get_db()
    session = get_session(db.news_engine)
    
    logger.info("正在查找重复记录 (基于标题和日期)...")
    
    # 查找重复的 (title, date) 组
    # 只处理中文新闻
    duplicates_query = session.query(
        News.title,
        cast(News.datetime, Date).label('date'),
        func.count(News.id).label('count'),
        func.array_agg(News.id).label('ids')
    ).filter(
        News.language == 'zh'
    ).group_by(
        News.title, 
        cast(News.datetime, Date)
    ).having(
        func.count(News.id) > 1
    )
    
    duplicates = duplicates_query.all()
    
    if not duplicates:
        logger.info("未发现重复记录")
        return

    logger.info(f"发现 {len(duplicates)} 组重复新闻，准备处理...")
    
    total_deleted = 0
    ids_to_delete = []
    
    for i, (title, date, count, ids) in enumerate(duplicates):
        # 查询这些 ID 的完整记录以检查 URL
        records = session.query(News).filter(News.id.in_(ids)).all()
        
        # 排序策略：
        # 1. 优先保留 URL 不是 notion:// 开头的 (False < True, so use not startswith)
        # 2. 优先保留 ID 最大的 (最新)
        records.sort(key=lambda x: (not x.url.startswith('notion://'), x.id), reverse=True)
        
        # 保留第一个，删除其余
        to_keep = records[0]
        to_delete = records[1:]
        
        for r in to_delete:
            ids_to_delete.append(r.id)
            
        if i % 1000 == 0:
            logger.info(f"已分析 {i}/{len(duplicates)} 组...")

    total_deleted = len(ids_to_delete)
    logger.info(f"分析完成，共发现 {total_deleted} 条待删除的重复记录")
    
    if dry_run:
        logger.info("[Dry Run] 不执行删除操作")
        return

    # 批量删除
    if ids_to_delete:
        logger.info("开始执行删除...")
        # 分批删除以避免 SQL 参数过多
        batch_size = 1000
        for i in range(0, len(ids_to_delete), batch_size):
            batch_ids = ids_to_delete[i:i+batch_size]
            session.query(News).filter(News.id.in_(batch_ids)).delete(synchronize_session=False)
            session.commit()
            logger.info(f"已删除 {min(i+batch_size, total_deleted)}/{total_deleted}")
            
    logger.info("清理完成！")
    session.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='清理重复新闻')
    parser.add_argument('--dry-run', action='store_true', help='仅分析不删除')
    args = parser.parse_args()
    
    cleanup_duplicates(dry_run=args.dry_run)
