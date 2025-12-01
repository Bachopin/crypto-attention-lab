#!/usr/bin/env python3
"""
重新计算包含中文新闻的注意力特征

导入中文新闻后，需要重新计算 2024-01-31 到 2025-11-29 期间的注意力特征
以确保 news_channel_score 包含中文新闻的影响

使用方法:
    python scripts/recompute_attention_with_chinese_news.py [--symbol ZEC] [--start-date 2024-01-31]
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging
from datetime import datetime, timezone, timedelta
from typing import List

from src.database.models import get_session
from src.data.db_storage import get_db
from src.features.calculators import calculate_composite_attention

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def recompute_attention_for_symbol(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    freq: str = 'D'
) -> int:
    """
    重新计算单个币种的注意力特征
    
    Args:
        symbol: 币种符号
        start_date: 开始日期
        end_date: 结束日期
        freq: 时间频率 (D, 4H, 1H, 15M)
    
    Returns:
        更新的记录数
    """
    db = get_db()
    
    logger.info(f"\n处理 {symbol} ({freq})...")
    logger.info(f"  时间范围: {start_date.date()} ~ {end_date.date()}")
    
    try:
        # 获取新闻数据（包括中文）
        news_df = db.get_news(
            symbols=[symbol],
            start=start_date,
            end=end_date,
        )
        
        if news_df is not None and not news_df.empty:
            zh_count = len(news_df[news_df['language'] == 'zh']) if 'language' in news_df.columns else 0
            en_count = len(news_df[news_df['language'] == 'en']) if 'language' in news_df.columns else 0
            total_count = len(news_df)
        else:
            zh_count = en_count = total_count = 0
        
        logger.info(f"  新闻数据: {total_count} 条 (中文: {zh_count}, 英文: {en_count})")
        
        # 获取价格数据（必需）
        price_df = db.get_prices(symbol, '1d', start_date, end_date)
        if price_df is None or price_df.empty:
            logger.warning(f"  {symbol}: 无价格数据，跳过")
            return 0
        
        logger.info(f"  价格数据: {len(price_df)} 条")
        
        # 获取 Google Trends 数据
        google_trends_df = db.get_google_trends(symbol, start_date, end_date)
        logger.info(f"  Google Trends: {len(google_trends_df) if google_trends_df is not None else 0} 条")
        
        # 获取 Twitter 数据
        twitter_df = db.get_twitter_volume(symbol, start_date, end_date)
        logger.info(f"  Twitter: {len(twitter_df) if twitter_df is not None else 0} 条")
        
        # 重新计算注意力分数
        logger.info(f"  重新计算注意力分数...")
        result_df = calculate_composite_attention(
            symbol=symbol,
            price_df=price_df,
            news_df=news_df,
            google_trends_df=google_trends_df,
            twitter_volume_df=twitter_df,
            freq=freq,
        )
        
        if result_df is None or result_df.empty:
            logger.warning(f"  {symbol}: 未生成注意力记录")
            return 0
        
        logger.info(f"  生成了 {len(result_df)} 条注意力记录")
        
        # 转换为记录列表格式并保存
        logger.info(f"  保存到数据库...")
        attention_records = result_df.to_dict('records')
        db.save_attention_features(symbol, attention_records, timeframe=freq)
        
        logger.info(f"  ✅ {symbol} 完成！")
        return len(result_df)
        
    except Exception as e:
        logger.error(f"  ❌ {symbol} 失败: {e}", exc_info=True)
        return 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='重新计算包含中文新闻的注意力特征')
    parser.add_argument(
        '--symbol',
        type=str,
        help='指定币种（默认：所有启用自动更新的币种）'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='2024-01-31',
        help='开始日期 (格式: YYYY-MM-DD, 默认: 2024-01-31)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='结束日期 (格式: YYYY-MM-DD, 默认: 今天)'
    )
    parser.add_argument(
        '--freq',
        type=str,
        default='D',
        choices=['D', '4H', '1H', '15M'],
        help='时间频率 (默认: D)'
    )
    
    args = parser.parse_args()
    
    # 解析日期
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        end_date = datetime.now(timezone.utc)
    
    print("\n" + "=" * 70)
    print("重新计算包含中文新闻的注意力特征")
    print("=" * 70)
    print(f"时间范围: {start_date.date()} ~ {end_date.date()}")
    print(f"频率: {args.freq}")
    print("=" * 70 + "\n")
    
    # 获取要处理的币种
    db = get_db()
    session = get_session(db.news_engine)
    
    try:
        from src.database.models import Symbol
        
        if args.symbol:
            symbols = session.query(Symbol).filter(
                Symbol.symbol == args.symbol.upper()
            ).all()
        else:
            # 只处理启用自动更新的币种
            symbols = session.query(Symbol).filter(
                Symbol.auto_update_price == True
            ).all()
        
        if not symbols:
            logger.error("未找到需要处理的币种")
            return 1
        
        logger.info(f"将处理 {len(symbols)} 个币种\n")
        
        total_updated = 0
        success_count = 0
        
        for sym in symbols:
            updated = recompute_attention_for_symbol(
                symbol=sym.symbol,
                start_date=start_date,
                end_date=end_date,
                freq=args.freq
            )
            
            if updated > 0:
                success_count += 1
                total_updated += updated
        
        print("\n" + "=" * 70)
        print(f"✅ 重新计算完成！")
        print(f"  成功: {success_count}/{len(symbols)} 个币种")
        print(f"  更新: {total_updated} 条记录")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == '__main__':
    sys.exit(main())
