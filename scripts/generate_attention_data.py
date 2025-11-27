#!/usr/bin/env python3
"""生成注意力特征（新闻驱动，多维特征）"""
import logging
from src.features.attention_features import process_attention_features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("="*60)
    # 默认日级
    process_attention_features('D')
    logger.info("Saved attention features to data/processed/attention_features_zec.csv")
    logger.info("="*60 + "\nCompleted!")
