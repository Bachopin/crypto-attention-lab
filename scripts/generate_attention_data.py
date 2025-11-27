#!/usr/bin/env python3
"""生成 90 天的 Attention Score 样例数据"""
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def load_price_data():
    """加载价格数据"""
    filepath = RAW_DIR / "price_ZECUSDT_1d.csv"
    df = pd.read_csv(filepath)
    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
    logger.info(f"Loaded {len(df)} rows from {filepath.name}")
    return df

def calculate_volatility(prices, window=7):
    """计算波动率"""
    returns = prices.pct_change()
    volatility = returns.rolling(window=window, min_periods=1).std() * 100
    return volatility.fillna(10.0)  # 填充NaN

def generate_attention_scores(price_df):
    """基于价格数据生成 attention scores"""
    df = price_df.copy()
    
    # 计算波动率
    df['volatility_7d'] = calculate_volatility(df['close'], window=7)
    
    # 计算价格变化
    df['price_change'] = df['close'].pct_change().fillna(0) * 100
    
    # 计算成交量变化  
    df['volume_change'] = df['volume'].pct_change().fillna(0) * 100
    
    # 基础注意力分数 (波动率归一化 0-40)
    vol_min = df['volatility_7d'].min()
    vol_max = df['volatility_7d'].max()
    if vol_max > vol_min:
        vol_normalized = ((df['volatility_7d'] - vol_min) / (vol_max - vol_min) * 40)
    else:
        vol_normalized = pd.Series([20.0] * len(df))
    
    # 成交量因子 (0-30)
    volume_factor = np.abs(df['volume_change']).clip(0, 50) / 50 * 30
    
    # 价格因子 (0-20)
    price_factor = np.abs(df['price_change']).clip(0, 10) / 10 * 20
    
    # 随机噪声
    np.random.seed(42)
    noise = np.random.normal(0, 5, len(df))
    
    # 综合计算
    attention_score = (vol_normalized + volume_factor + price_factor + noise).clip(0, 100)
    
    # 平滑处理
    attention_score = pd.Series(attention_score).rolling(window=3, min_periods=1).mean()
    
    # 新闻数量 (基于注意力分数)
    news_count = (attention_score / 20).fillna(0).apply(int) + np.random.randint(1, 4, len(df))
    news_count = news_count.clip(1, 10)
    
    # 情感分数
    avg_sentiment = (df['price_change'] / 10).clip(-1, 1) + np.random.normal(0, 0.2, len(df))
    avg_sentiment = avg_sentiment.clip(-1, 1)
    
    result = pd.DataFrame({
        'datetime': df['datetime'],
        'attention_score': attention_score.round(2),
        'news_count': news_count.astype(int),
        'avg_sentiment': avg_sentiment.round(3),
        'volatility_7d': df['volatility_7d'].round(2)
    })
    
    return result

def save_attention_data(df):
    """保存注意力数据"""
    filepath = PROCESSED_DIR / "attention_features_zec.csv"
    df.to_csv(filepath, index=False)
    logger.info(f"Saved {len(df)} rows to {filepath}")
    logger.info(f"Attention Score: min={df['attention_score'].min():.1f}, max={df['attention_score'].max():.1f}, avg={df['attention_score'].mean():.1f}")

if __name__ == "__main__":
    logger.info("="*60)
    price_df = load_price_data()
    attention_df = generate_attention_scores(price_df)
    save_attention_data(attention_df)
    logger.info("="*60 + "\nCompleted!")
