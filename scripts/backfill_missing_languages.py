#!/usr/bin/env python3
"""
回填数据库中缺失的 language 字段
使用 DEFAULT_SOURCE_LANGUAGE 配置推断语言
"""
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import News, get_session, get_engine
from src.config.attention_channels import DEFAULT_SOURCE_LANGUAGE
from src.config.settings import NEWS_DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_languages():
    """回填缺失的 language 字段"""
    engine = get_engine(NEWS_DATABASE_URL)
    session = get_session(engine)
    
    try:
        # 查询所有 language 为 None 的记录
        none_lang_news = session.query(News).filter(News.language.is_(None)).all()
        
        logger.info(f"找到 {len(none_lang_news)} 条 language 为 None 的记录")
        
        updated_count = 0
        unknown_sources = set()
        
        for news in none_lang_news:
            source = news.source
            
            # 从配置中获取语言
            language = DEFAULT_SOURCE_LANGUAGE.get(source)
            
            if language:
                news.language = language
                updated_count += 1
            else:
                # 记录未知来源
                unknown_sources.add(source)
                # 默认设置为英文
                news.language = 'en'
                updated_count += 1
        
        # 批量提交
        session.commit()
        logger.info(f"成功更新 {updated_count} 条记录")
        
        if unknown_sources:
            logger.warning(f"以下 {len(unknown_sources)} 个来源未在配置中找到，已默认设置为 'en':")
            for source in sorted(unknown_sources):
                count = sum(1 for n in none_lang_news if n.source == source)
                logger.warning(f"  - {source}: {count} 条")
        
        # 验证结果
        remaining_none = session.query(News).filter(News.language.is_(None)).count()
        logger.info(f"回填完成，剩余 language 为 None 的记录: {remaining_none}")
        
    except Exception as e:
        session.rollback()
        logger.error(f"回填失败: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logger.info("开始回填缺失的 language 字段...")
    backfill_languages()
    logger.info("回填完成!")
