import requests
import pandas as pd
from datetime import datetime
from src.config.settings import RAW_DATA_DIR

RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_and_save_price_coingecko(coin_id='zcash', vs_currency='usd', days=365, filename=None):
    """
    使用 CoinGecko 的 market_chart 接口获取历史价格并保存为 CSV。
    - coin_id: CoinGecko 上的币种 id（例如: 'zcash'）
    - vs_currency: 计价货币（例如: 'usd'）
    - days: 最近多少天（例如 365）

    返回保存的文件路径（Path 对象的字符串）。
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": vs_currency, "days": days, "interval": "daily"}

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    prices = data.get('prices', [])  # list of [timestamp(ms), price]
    volumes = data.get('total_volumes', [])  # list of [timestamp(ms), volume]

    if not prices:
        raise RuntimeError('No price data returned from CoinGecko')

    df_prices = pd.DataFrame(prices, columns=['timestamp', 'price'])
    df_vols = pd.DataFrame(volumes, columns=['timestamp', 'volume'])

    # 合并并按日期分组计算 OHLCV
    df = pd.merge(df_prices, df_vols, on='timestamp', how='left')
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df['date'] = df['datetime'].dt.floor('D')

    grouped = df.groupby('date').agg(
        open=('price', 'first'),
        high=('price', 'max'),
        low=('price', 'min'),
        close=('price', 'last'),
        volume=('volume', 'sum')
    ).reset_index()

    grouped['timestamp'] = (grouped['date'].astype('int64') // 10**6)
    grouped = grouped[['timestamp', 'open', 'high', 'low', 'close', 'volume', 'date']]
    grouped = grouped.rename(columns={'date': 'datetime'})

    # 保存到数据库
    from src.data.db_storage import get_db
    
    # 转换 symbol 格式 (zcash -> ZEC)
    # 这里简单映射，实际可能需要更复杂的映射或传入 symbol 参数
    symbol_map = {
        'zcash': 'ZEC',
        'bitcoin': 'BTC',
        'ethereum': 'ETH'
    }
    symbol = symbol_map.get(coin_id, coin_id.upper())
    
    records = grouped.to_dict('records')
    try:
        db = get_db()
        db.save_prices(symbol, '1d', records)
        print(f"Saved {len(records)} price records for {symbol} to database")
        return f"db:{symbol}:1d"
    except Exception as e:
        raise RuntimeError(f"Failed to save prices to database: {e}")


if __name__ == '__main__':
    print(fetch_and_save_price_coingecko(days=90))
