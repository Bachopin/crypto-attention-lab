#!/usr/bin/env python3
"""
导入 Notion 导出的 CSV 数据到数据库

从 Notion 导出的 CSV 文件导入中文加密货币新闻到 PostgreSQL 数据库
支持批量导入、去重、自动过滤 AI总结 分类

使用方法：
    python scripts/import_notion_export.py [--file <path>] [--dry-run] [--batch-size 100]
"""

import csv
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.models import get_session
from src.data.db_storage import get_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 排除的分类
EXCLUDED_CATEGORIES = ["AI总结"]

# 常见代币符号列表（用于从标题提取）
COMMON_SYMBOLS = {
    'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'MATIC', 'AVAX',
    'LINK', 'UNI', 'LTC', 'ATOM', 'XLM', 'ALGO', 'VET', 'ICP', 'FIL', 'HBAR',
    'APT', 'ARB', 'OP', 'NEAR', 'SUI', 'SEI', 'TIA', 'INJ', 'RUNE', 'RNDR',
    'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDD', 'USDP', 'GUSD', 'PYUSD',
    'ZEC', 'BCH', 'ETC', 'DASH', 'ZEN', 'XMR', 'KDA', 'CFX', 'CKB', 'FTM',
    'TNSR', 'QUSD', 'CELO', 'CCIP', 'TAO', 'WLD', 'PEPE', 'SHIB', 'FLOKI',
    'AAVE', 'CRV', 'MKR', 'SNX', 'COMP', 'YFI', 'SUSHI', '1INCH', 'BAL',
    'MON', 'HYPE', 'JUP', 'PYTH', 'WIF', 'BONK', 'ORDI', 'BLUR',
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


def extract_symbols_from_text(text: str, existing_symbols: str = "") -> str:
    """
    从文本中提取代币符号，合并已有的符号
    
    Args:
        text: 新闻标题或内容
        existing_symbols: 已有的符号（从 CSV 的 币种/赛道 列）
    
    Returns:
        逗号分隔的符号字符串
    """
    symbols = set()
    
    # 先添加已有的符号
    if existing_symbols:
        for s in existing_symbols.split(','):
            s = s.strip().upper()
            if s and len(s) <= 10:
                symbols.add(s)
    
    # 1. 提取英文符号（大写字母）
    for symbol in COMMON_SYMBOLS:
        pattern = r'\b' + re.escape(symbol) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            symbols.add(symbol)
    
    # 2. 提取中文代币名称
    for cn_name, symbol in CHINESE_TOKEN_MAP.items():
        if cn_name in text:
            symbols.add(symbol)
    
    # 3. 提取 /USDT 格式
    usdt_matches = re.findall(r'([A-Z]{2,10})/USDT', text.upper())
    symbols.update(usdt_matches)
    
    return ','.join(sorted(symbols)) if symbols else ''


def parse_notion_date(date_str: str) -> Optional[datetime]:
    """
    解析 Notion 导出的日期格式
    
    支持格式：
    - "2022年11月21日 12:03"
    - "2022年11月21日 04:03 (UTC)"
    - "2023年4月30日 → 2023年5月10日" (取开始日期)
    - "2023/04/30 → 2023/05/10"
    
    Args:
        date_str: Notion 导出的日期字符串
    
    Returns:
        datetime 对象（UTC 时区）
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # 处理日期范围（取开始日期）
    if '→' in date_str:
        date_str = date_str.split('→')[0].strip()
    
    # 检查是否是 UTC 时间
    is_utc = '(UTC)' in date_str
    date_str = date_str.replace('(UTC)', '').strip()
    
    try:
        # 格式: "2022年11月21日 12:03"
        if '年' in date_str:
            # 提取年月日时分
            match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})?:?(\d{2})?', date_str)
            if match:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                hour = int(match.group(4)) if match.group(4) else 0
                minute = int(match.group(5)) if match.group(5) else 0
                
                dt = datetime(year, month, day, hour, minute)
                if is_utc:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    # 假设是北京时间 (UTC+8)
                    from datetime import timedelta
                    dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
                
                return dt
        
        # 格式: "2023/04/30"
        elif '/' in date_str:
            parts = date_str.split('/')
            if len(parts) >= 3:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2].split()[0])
                dt = datetime(year, month, day, tzinfo=timezone.utc)
                return dt
    
    except Exception as e:
        logger.debug(f"解析日期失败: {date_str}, 错误: {e}")
    
    return None


def parse_csv_record(row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    解析单条 CSV 记录
    
    Args:
        row: CSV 行数据（字典）
    
    Returns:
        转换后的新闻记录，如果应跳过则返回 None
    """
    # 获取标题（处理 BOM）
    title = row.get('\ufeffName') or row.get('Name') or ''
    title = title.strip()
    
    if not title:
        return None
    
    # 检查分类，排除 AI总结
    category = row.get('分类', '').strip()
    if category in EXCLUDED_CATEGORIES:
        return None
    
    # 解析时间（优先使用 Time 列，其次 Created Date）
    time_str = row.get('Time', '').strip()
    created_str = row.get('Created Date', '').strip()
    
    dt = parse_notion_date(time_str) or parse_notion_date(created_str)
    
    if not dt:
        # 无法解析时间，跳过
        logger.debug(f"无法解析时间: Time={time_str}, Created={created_str}")
        return None
    
    # 转换为 UTC
    dt_utc = dt.astimezone(timezone.utc)
    timestamp = int(dt_utc.timestamp() * 1000)  # 毫秒时间戳
    
    # 获取 URL
    url = row.get('相关链接', '').strip()
    
    # 确定来源
    source = 'PANews'  # 默认
    if url:
        if 'odaily' in url.lower():
            source = 'Odaily'
        elif 'panews' in url.lower():
            source = 'PANews'
        elif 'theblock' in url.lower():
            source = 'TheBlock'
        elif 'coindesk' in url.lower():
            source = 'CoinDesk'
        elif 'twitter.com' in url.lower() or 'x.com' in url.lower():
            source = 'Twitter'
        elif 'chaincatcher' in url.lower():
            source = 'ChainCatcher'
    
    # 提取代币符号
    coin_track = row.get('币种/赛道', '').strip()
    summary = row.get('概要', '').strip()
    full_text = f"{title} {summary} {coin_track}"
    symbols = extract_symbols_from_text(full_text, coin_track)
    
    # 获取其他字段
    level = row.get('级别', '').strip()
    direction = row.get('多空', '').strip()
    nature = row.get('性质', '').strip()
    
    # 生成唯一 URL（如果没有 URL，用标题+时间生成）
    if not url:
        url = f"notion://news/{timestamp}/{hash(title) % 1000000}"
    
    return {
        'timestamp': timestamp,
        'datetime': dt_utc.isoformat(),
        'title': title,
        'url': url,
        'source': source,
        'platform': 'news',
        'language': 'zh',
        'symbols': symbols,
        'author': None,
        'node': source,
        'node_id': f"news:{source}",
        'relevance': 'related',
        'source_weight': 1.0,
        'sentiment_score': None,
        'tags': ','.join(filter(None, [category, nature, level, direction])),
    }


def parse_csv_file(csv_path: str) -> List[Dict[str, Any]]:
    """
    解析 Notion 导出的 CSV 文件
    
    Args:
        csv_path: CSV 文件路径
    
    Returns:
        解析后的新闻列表
    """
    logger.info(f"读取文件: {csv_path}")
    
    news_list = []
    skipped_ai = 0
    skipped_invalid = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            # 检查分类，统计跳过的 AI总结
            category = row.get('分类', '').strip()
            if category in EXCLUDED_CATEGORIES:
                skipped_ai += 1
                continue
            
            record = parse_csv_record(row)
            if record:
                news_list.append(record)
            else:
                skipped_invalid += 1
    
    logger.info(f"解析完成: {len(news_list)} 条有效记录")
    logger.info(f"  跳过 AI总结: {skipped_ai} 条")
    logger.info(f"  跳过无效记录: {skipped_invalid} 条")
    
    return news_list


def import_to_database(news_list: List[Dict[str, Any]], batch_size: int = 500):
    """
    批量导入新闻到数据库
    
    Args:
        news_list: 新闻列表
        batch_size: 批量大小
    """
    total = len(news_list)
    logger.info(f"开始导入 {total} 条新闻到数据库...")
    
    db = get_db()
    
    for i in range(0, total, batch_size):
        batch = news_list[i:i+batch_size]
        
        try:
            db.save_news(batch)
            progress = min(i + batch_size, total)
            logger.info(f"进度: {progress}/{total} ({progress*100//total}%)")
        except Exception as e:
            logger.error(f"批次导入失败 (offset {i}): {e}")
            continue
    
    logger.info(f"导入完成！")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='导入 Notion 导出的 CSV 数据')
    parser.add_argument(
        '-f', '--file',
        default='data/raw/捕风捉影 42565a03220542b68685cf6838954a44_all.csv',
        help='CSV 文件路径'
    )
    parser.add_argument(
        '-b', '--batch-size',
        type=int,
        default=500,
        help='批量大小（默认 500）'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅解析文件，不导入数据库'
    )
    parser.add_argument(
        '--skip',
        type=int,
        default=0,
        help='跳过前 N 条数据'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='最多导入 N 条数据'
    )
    
    args = parser.parse_args()
    
    # 检查文件
    csv_path = Path(args.file)
    if not csv_path.exists():
        logger.error(f"文件不存在: {csv_path}")
        return 1
    
    # 解析 CSV
    news_list = parse_csv_file(str(csv_path))
    
    if not news_list:
        logger.warning("未解析到任何有效新闻")
        return 1
    
    # 应用 skip 和 limit
    if args.skip > 0:
        logger.info(f"跳过前 {args.skip} 条")
        news_list = news_list[args.skip:]
    
    if args.limit:
        logger.info(f"限制最多 {args.limit} 条")
        news_list = news_list[:args.limit]
    
    logger.info(f"\n待导入: {len(news_list)} 条")
    
    # 统计信息
    sources = {}
    for news in news_list:
        src = news.get('source', 'Unknown')
        sources[src] = sources.get(src, 0) + 1
    
    logger.info(f"\n来源分布:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        logger.info(f"  {src}: {count}")
    
    # 时间范围
    timestamps = [n['timestamp'] for n in news_list if n['timestamp']]
    if timestamps:
        min_ts = min(timestamps)
        max_ts = max(timestamps)
        min_dt = datetime.fromtimestamp(min_ts / 1000, tz=timezone.utc)
        max_dt = datetime.fromtimestamp(max_ts / 1000, tz=timezone.utc)
        logger.info(f"\n时间范围: {min_dt.date()} 至 {max_dt.date()}")
    
    # 样例
    logger.info("\n样例数据:")
    for i, news in enumerate(news_list[:3]):
        logger.info(f"\n[{i+1}] {news['title'][:60]}...")
        logger.info(f"    URL: {news['url'][:60] if news['url'] else 'N/A'}...")
        logger.info(f"    时间: {news['datetime']}")
        logger.info(f"    来源: {news['source']}")
        logger.info(f"    符号: {news['symbols'] if news['symbols'] else '无'}")
    
    if args.dry_run:
        logger.info("\n[Dry run 模式，不导入数据库]")
        return 0
    
    # 确认导入
    logger.info("\n" + "=" * 50)
    confirm = input(f"确认导入 {len(news_list)} 条新闻到数据库？(y/N): ")
    if confirm.lower() != 'y':
        logger.info("已取消")
        return 0
    
    # 导入
    import_to_database(news_list, args.batch_size)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
