
import pandas as pd
from src.data.db_storage import get_db
from src.config.settings import TRACKED_SYMBOLS

def check_news_distribution():
    db = get_db()
    # 获取所有新闻
    df = db.get_news(start=pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=30))
    
    if df.empty:
        print("No news found in database.")
        return

    print(f"Total news items: {len(df)}")
    
    # 统计每天的新闻数量
    df['date'] = df['datetime'].dt.date
    daily_counts = df.groupby('date').size()
    print("\nDaily News Counts (All):")
    print(daily_counts.tail(10))
    
    # 统计各币种每天的新闻数量
    print("\nDaily News Counts by Symbol:")
    for symbol_pair in TRACKED_SYMBOLS:
        base_symbol = symbol_pair.split('/')[0]
        # 简单的字符串匹配模拟 detect_symbols
        symbol_news = df[df['symbols'].str.contains(base_symbol, case=False, na=False)]
        print(f"\n--- {base_symbol} ---")
        print(symbol_news.groupby('date').size().tail(10))

if __name__ == "__main__":
    check_news_distribution()
