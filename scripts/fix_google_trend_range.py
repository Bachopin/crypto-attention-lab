# 检查并补齐 Google Trend 区间脚本
import pandas as pd
from src.data.db_storage import get_db
from src.data.google_trends_fetcher import get_google_trends_series

def main():
    db = get_db()
    syms = db.get_all_symbols()
    print('SYMBOLS:', syms)
    for sym in syms:
        price = db.get_prices(sym, '1d')
        if price is None or price.empty:
            print(f'{sym}: No price data')
            continue
        gt = db.get_google_trends(sym)
        pmin, pmax = price['datetime'].min(), price['datetime'].max()
        gtmin, gtmax = None, None
        if gt is not None and not gt.empty:
            gtmin, gtmax = gt['datetime'].min(), gt['datetime'].max()
        print(f'{sym}: price=({pmin}, {pmax}), google_trend=({gtmin}, {gtmax})')
        # 判断是否需要补齐
        if gtmin is None or gtmax is None or gtmin > pmin or gtmax < pmax:
            print(f'  -> 补齐 {sym} Google Trend 区间...')
            df = get_google_trends_series(sym, pmin, pmax, force_refresh=True)
            print(f'  -> 补齐后行数: {len(df)}')
        else:
            print(f'  -> 已对齐')

if __name__ == '__main__':
    main()
