#!/usr/bin/env python3
"""生成注意力特征（新闻驱动，多维特征）"""
import logging
import sys
from pathlib import Path

# 确保项目根目录可被导入
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.features.attention_features import process_attention_features
from src.config.settings import TRACKED_SYMBOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("="*60)
    logger.info("Generating attention features and saving to database...")
    
    for symbol_pair in TRACKED_SYMBOLS:
        # symbol_pair 格式如 "ZEC/USDT"
        base_symbol = symbol_pair.split('/')[0]
        logger.info(f"Processing attention features for {base_symbol}...")
        try:
            # 默认日级
            process_attention_features(symbol=base_symbol, freq='D')
        except Exception as e:
            logger.error(f"Failed to process attention features for {base_symbol}: {e}")
            
    logger.info("✅ Attention features saved to database successfully!")
    logger.info("="*60 + "\nCompleted!")
