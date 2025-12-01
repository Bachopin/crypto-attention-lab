#!/usr/bin/env python3
"""
导入中文新闻 JSON 数据到数据库

从 Aggregate.json 文件导入中文加密货币新闻到 PostgreSQL 数据库
支持批量导入、去重、代币符号提取
"""

import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
import logging

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import get_session
from src.data.db_storage import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 常见代币符号列表（用于提取）
COMMON_SYMBOLS = {
    'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'MATIC', 'AVAX',
    'LINK', 'UNI', 'LTC', 'ATOM', 'XLM', 'ALGO', 'VET', 'ICP', 'FIL', 'HBAR',
    'APT', 'ARB', 'OP', 'NEAR', 'SUI', 'SEI', 'TIA', 'INJ', 'RUNE', 'RNDR',
    'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDD', 'USDP', 'GUSD', 'PYUSD',
    'ZEC', 'BCH', 'ETC', 'DASH', 'ZEN', 'XMR', 'KDA', 'CFX', 'CKB', 'FTM',
    'TNSR', 'QUSD', 'CELO', 'CCIP', 'TAO', 'WLD', 'PEPE', 'SHIB', 'FLOKI',
}

# 中文代币名称映射
CHINESE_TOKEN_MAP = {
    '比特币': 'BTC',
    '以太坊': 'ETH', 
    '以太币': 'ETH',
    '币安币': 'BNB',
    '狗狗币': 'DOGE',
    '瑞波币': 'XRP',
    '莱特币': 'LTC',
    '艾达币': 'ADA',
    '波卡': 'DOT',
    '索拉纳': 'SOL',
    '柴犬币': 'SHIB',
}


def extract_symbols_from_text(text: str) -> List[str]:
    """
    从文本中提取代币符号
    
    Args:
        text: 新闻标题或内容
    
    Returns:
        提取到的代币符号列表
    """
    symbols = set()
    
    # 1. 提取英文符号（大写字母）
    for symbol in COMMON_SYMBOLS:
        # 匹配独立的符号（避免误匹配）
        pattern = r'\b' + re.escape(symbol) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            symbols.add(symbol)
    
    # 2. 提取中文代币名称
    for cn_name, symbol in CHINESE_TOKEN_MAP.items():
        if cn_name in text:
            symbols.add(symbol)
    
    # 3. 提取 /USDT 格式
    usdt_matches = re.findall(r'([A-Z]{2,10})/USDT', text)
    symbols.update(usdt_matches)
    
    return sorted(list(symbols))


def parse_aggregate_json(json_path: str) -> List[Dict[str, Any]]:
    """
    解析 Aggregate.json 文件
    
    Args:
        json_path: JSON 文件路径
    
    Returns:
        解析后的新闻列表
    """
    logger.info(f"读取文件: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    news_list = []
    
    for item in data:
        if 'json' not in item or 'data' not in item['json']:
            continue
        
        for news_item in item['json']['data']:
            try:
                # 提取基本信息
                title = news_item.get('Title', '').strip()
                link = news_item.get('Link', '')
                pub_date = news_item.get('pubDate') or news_item.get('isoDate')
                content = news_item.get('contentSnippet', '') or news_item.get('content', '')
                
                if not title or not link:
                    continue
                
                # 解析发布时间
                if pub_date:
                    if isinstance(pub_date, (int, float)):
                        # 时间戳（毫秒）
                        dt = datetime.fromtimestamp(pub_date / 1000, tz=timezone.utc)
                    else:
                        # ISO 格式字符串
                        dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                else:
                    dt = datetime.now(timezone.utc)
                
                # 提取代币符号
                full_text = f"{title} {content[:500]}"  # 只用前500字符提取符号
                symbols = extract_symbols_from_text(full_text)
                
                # 确定来源
                source = 'PANews'
                if 'odaily' in link.lower():
                    source = 'Odaily'
                elif 'panews' in link.lower():
                    source = 'PANews'
                
                news_list.append({
                    'timestamp': int(dt.timestamp() * 1000),  # 毫秒时间戳
                    'datetime': dt.isoformat(),  # ISO 格式字符串
                    'title': title,
                    'url': link,
                    'source': source,
                    'platform': 'news',
                    'language': 'zh',
                    'symbols': ','.join(symbols) if symbols else '',  # 逗号分隔的字符串
                    'author': None,
                    'node': source,
                    'node_id': f"news:{source}",
                    'relevance': 'related',
                    'source_weight': 1.0,
                    'sentiment_score': None,
                    'tags': '',
                })
                
            except Exception as e:
                logger.warning(f"解析新闻项失败: {e}, item: {news_item.get('Title', 'Unknown')[:50]}")
                continue
    
    return news_list


def import_to_database(news_list: List[Dict[str, Any]], batch_size: int = 100):
    """
    批量导入新闻到数据库
    
    Args:
        news_list: 新闻列表
        batch_size: 批量大小
    """
    total = len(news_list)
    imported = 0
    skipped = 0
    
    logger.info(f"开始导入 {total} 条新闻...")
    
    db = get_db()
    
    for i in range(0, total, batch_size):
        batch = news_list[i:i+batch_size]
        
        try:
            db.save_news(batch)
            # save_news 没有返回值，需要手动统计
            imported += len(batch)
            
            logger.info(
                f"批次 {i//batch_size + 1}/{(total + batch_size - 1)//batch_size}: "
                f"处理 {len(batch)} 条"
            )
        except Exception as e:
            logger.error(f"批次导入失败: {e}")
            continue
    
    logger.info(f"\n导入完成！")
    logger.info(f"  总计: {total} 条")
    logger.info(f"  处理: {imported} 条")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='导入中文新闻 JSON 数据')
    parser.add_argument(
        '-f', '--file',
        default='data/raw/Aggregate.json',
        help='JSON 文件路径'
    )
    parser.add_argument(
        '-b', '--batch-size',
        type=int,
        default=100,
        help='批量大小'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅解析文件，不导入数据库'
    )
    
    args = parser.parse_args()
    
    # 检查文件是否存在
    json_path = Path(args.file)
    if not json_path.exists():
        logger.error(f"文件不存在: {json_path}")
        return 1
    
    # 解析 JSON
    news_list = parse_aggregate_json(str(json_path))
    
    if not news_list:
        logger.warning("未解析到任何新闻")
        return 1
    
    logger.info(f"解析到 {len(news_list)} 条新闻")
    
    # 显示样例
    logger.info("\n样例数据:")
    for i, news in enumerate(news_list[:3]):
        logger.info(f"\n[{i+1}] {news['title']}")
        logger.info(f"    URL: {news['url']}")
        logger.info(f"    时间: {news['datetime']}")
        logger.info(f"    来源: {news['source']}")
        logger.info(f"    符号: {news['symbols'] if news['symbols'] else '无'}")
    
    if args.dry_run:
        logger.info("\nDry run 模式，不导入数据库")
        return 0
    
    # 导入数据库
    import_to_database(news_list, args.batch_size)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
