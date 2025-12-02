#!/usr/bin/env python3
"""
清理数据库中的 Tags
移除无意义的中文 Tags、表情符号和 None
"""
import sys
import logging
import re
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.db_storage import get_db
from src.database.models import News, get_session

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 需要移除的 Tags 列表（完全匹配）
REMOVE_TAGS = {
    '新闻', '快讯', '公告', 'None', 'none', 'null', 
    '事实', '传闻', '流行', '创新', '其它',
    '看多', '看空', 'FUD', 'ALT', 'BTC', 'ETH', 'NFT', 'Gamefi'
}

# 需要保留的英文 Tags (白名单，如果需要严格控制)
# 目前策略是：移除中文、移除表情、移除特定无意义词

def clean_tag_string(tags_str: str) -> str:
    if not tags_str:
        return ''
    
    new_tags = set()
    for tag in tags_str.split(','):
        tag = tag.strip()
        if not tag:
            continue
            
        # 1. 移除表情符号 (⭐ 等)
        # 简单判断：如果包含非 ASCII 且不是中文（虽然这里我们也要移除中文）
        # 或者直接用正则匹配 ⭐
        if '⭐' in tag:
            continue
            
        # 2. 移除特定无意义词
        if tag in REMOVE_TAGS:
            continue
            
        # 3. 移除纯中文 Tags (如果需要)
        # 匹配包含中文字符的 tag
        if re.search(r'[\u4e00-\u9fa5]', tag):
            continue
            
        new_tags.add(tag)
    
    return ','.join(sorted(new_tags))

def cleanup_tags(dry_run: bool = False):
    db = get_db()
    session = get_session(db.news_engine)
    
    logger.info("开始扫描需要清理 Tags 的新闻...")
    
    # 获取所有有 tags 的新闻
    news_list = session.query(News).filter(News.tags != '', News.tags != None).all()
    
    updated_count = 0
    
    for news in news_list:
        original_tags = news.tags
        cleaned_tags = clean_tag_string(original_tags)
        
        if original_tags != cleaned_tags:
            if not dry_run:
                news.tags = cleaned_tags
            updated_count += 1
            
            if updated_count <= 10:  # 打印前 10 个样例
                logger.info(f"清理: [{original_tags}] -> [{cleaned_tags}]")
    
    logger.info(f"扫描完成，共 {len(news_list)} 条记录")
    logger.info(f"需要更新: {updated_count} 条")
    
    if dry_run:
        logger.info("[Dry Run] 不执行更新")
    else:
        if updated_count > 0:
            session.commit()
            logger.info("更新已提交")
        else:
            logger.info("无需更新")
            
    session.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='清理新闻 Tags')
    parser.add_argument('--dry-run', action='store_true', help='仅分析不更新')
    args = parser.parse_args()
    
    cleanup_tags(dry_run=args.dry_run)
