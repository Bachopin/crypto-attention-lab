
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import random
from src.data.db_storage import get_db
from src.config.settings import TRACKED_SYMBOLS

def generate_mock_news():
    print("Generating mock news data due to API rate limits...")
    
    db = get_db()
    news_list = []
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)
    
    sources = ["CoinDesk", "CoinTelegraph", "CryptoSlate", "Decrypt", "The Block"]
    
    for symbol_pair in TRACKED_SYMBOLS:
        symbol = symbol_pair.split('/')[0]
        print(f"Generating for {symbol}...")
        
        current_date = start_date
        while current_date <= end_date:
            # 每天随机生成 5-15 条新闻
            daily_count = random.randint(5, 15)
            
            # 模拟一些波动，让曲线好看点
            if random.random() > 0.8:
                daily_count += random.randint(10, 20) # 突发事件
                
            for _ in range(daily_count):
                # 随机时间
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                dt = current_date.replace(hour=hour, minute=minute)
                
                news_list.append({
                    "timestamp": int(dt.timestamp() * 1000),
                    "datetime": dt,
                    "title": f"Mock News for {symbol}: Market update and analysis #{random.randint(1000, 9999)}",
                    "source": random.choice(sources),
                    "url": f"https://example.com/mock/{symbol}/{int(dt.timestamp())}",
                    "symbols": symbol,
                    "relevance": "direct",
                    "source_weight": random.uniform(0.5, 1.0),
                    "sentiment_score": random.uniform(-0.8, 0.8),
                    "tags": f"{symbol},Crypto,Market"
                })
            
            current_date += timedelta(days=1)
            
    # 保存到数据库
    if news_list:
        df = pd.DataFrame(news_list)
        # 转换为 dict list
        records = df.to_dict('records')
        db.save_news(records)
        print(f"✅ Saved {len(records)} mock news items to database")
    else:
        print("No mock data generated")

if __name__ == "__main__":
    generate_mock_news()
