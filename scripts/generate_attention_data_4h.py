#!/usr/bin/env python3
"""
生成 4 小时级注意力特征（新闻驱动，多维特征）

本脚本遍历重点币种，生成 4H 级别的 Attention 特征并保存到数据库。

使用方法：
    python scripts/generate_attention_data_4h.py [--symbols BTC,ETH,SOL]

参数：
    --symbols: 可选，逗号分隔的币种列表。如不指定则使用预设的重点币种列表。
    --dry-run: 可选，仅输出 DataFrame 而不保存到数据库。

4H 特征说明：
- 新闻通道：按 4H 窗口精确聚合新闻数据
- Google Trends：日级数据均匀填充到 4H 桶（近似假设：同一天内各 4H 桶值相同）
- Twitter：日级数据均匀填充到 4H 桶（近似假设：同一天内各 4H 桶值相同）
- Rolling window：30 天 = 180 个 4H 周期
- 变化率周期：7 天 = 42 个 4H 周期，30 天 = 180 个 4H 周期

注意事项：
- Google Trends 和 Twitter 的 4H 填充是近似方案，未来可改进为插值或接入小时级 API
- 首次运行会自动在数据库中创建 timeframe 字段（如果尚不存在）
"""
import argparse
import logging
import sys
from pathlib import Path

# 确保项目根目录可被导入
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.attention_features import process_attention_features

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 预设的重点币种列表
# 包含：大币（BTC, ETH）+ 重点山寨（SOL, XRP, DOGE, ADA, AVAX, DOT, LINK, UNI, ATOM, ZEC）
DEFAULT_SYMBOLS = [
    'BTC',   # Bitcoin - 市值第一
    'ETH',   # Ethereum - 市值第二
    'SOL',   # Solana - 高性能公链
    'XRP',   # Ripple - 跨境支付
    'DOGE',  # Dogecoin - Meme 代表
    'ADA',   # Cardano - 学术派公链
    'AVAX',  # Avalanche - 高速公链
    'DOT',   # Polkadot - 跨链生态
    'LINK',  # Chainlink - 预言机龙头
    'UNI',   # Uniswap - DEX 龙头
    'ATOM',  # Cosmos - 跨链生态
    'ZEC',   # Zcash - 隐私币代表
]


def parse_args():
    parser = argparse.ArgumentParser(
        description='生成 4H 级别的注意力特征',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--symbols',
        type=str,
        default=None,
        help='逗号分隔的币种列表，如 BTC,ETH,SOL。不指定则使用预设列表。'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅输出 DataFrame 信息而不保存到数据库'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    # 解析币种列表
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',') if s.strip()]
    else:
        symbols = DEFAULT_SYMBOLS
    
    logger.info("=" * 70)
    logger.info("Generating 4H attention features for %d symbols", len(symbols))
    logger.info("Symbols: %s", ', '.join(symbols))
    if args.dry_run:
        logger.info("DRY RUN MODE: Will not save to database")
    logger.info("=" * 70)
    
    success_count = 0
    fail_count = 0
    
    for symbol in symbols:
        logger.info("-" * 50)
        logger.info("Processing 4H attention features for %s...", symbol)
        
        try:
            # 调用 process_attention_features 并传入 freq='4H'
            result = process_attention_features(
                symbol=symbol,
                freq='4H',
                save_to_db=not args.dry_run
            )
            
            if result is not None and not result.empty:
                logger.info(
                    "✅ %s: Generated %d rows, date range: %s to %s",
                    symbol,
                    len(result),
                    result['datetime'].min().strftime('%Y-%m-%d %H:%M'),
                    result['datetime'].max().strftime('%Y-%m-%d %H:%M')
                )
                
                # 打印一些统计信息
                logger.info(
                    "   Stats: news_count(sum=%.0f, max=%.0f), composite_attention(mean=%.2f, std=%.2f)",
                    result['news_count'].sum(),
                    result['news_count'].max(),
                    result['composite_attention_score'].mean(),
                    result['composite_attention_score'].std()
                )
                
                success_count += 1
            else:
                logger.warning("⚠️ %s: No data generated (possibly no news data)", symbol)
                fail_count += 1
                
        except Exception as e:
            logger.error("❌ %s: Failed to process - %s", symbol, str(e))
            fail_count += 1
    
    logger.info("=" * 70)
    logger.info("Summary: %d succeeded, %d failed out of %d symbols", 
                success_count, fail_count, len(symbols))
    
    if args.dry_run:
        logger.info("DRY RUN completed. No data was saved to database.")
    else:
        logger.info("✅ 4H Attention features saved to database successfully!")
    
    logger.info("=" * 70)
    
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
