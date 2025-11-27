import ccxt
import pandas as pd
import time
import random
import logging
import os
from datetime import datetime, timedelta
from src.config.settings import RAW_DATA_DIR

logger = logging.getLogger(__name__)


def _ensure_raw_dir():
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_proxies_from_env():
    """从环境变量构建 requests 兼容的代理配置字典。优先使用 ALL_PROXY（可为 socks5h）。"""
    proxies = {}
    all_proxy = os.environ.get('ALL_PROXY') or os.environ.get('all_proxy')
    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    if all_proxy:
        proxies['http'] = all_proxy
        proxies['https'] = all_proxy
    if http_proxy:
        proxies['http'] = http_proxy
    if https_proxy:
        proxies['https'] = https_proxy
    return proxies or None


def _set_binance_base(exchange: ccxt.binance, hostname: str):
    """设置 ccxt binance 的 hostname（例如 api1.binance.com）。避免直接改 urls，交给 ccxt 处理版本路径。"""
    try:
        exchange.hostname = hostname
    except Exception:
        pass


def _safe_symbol(symbol: str) -> str:
    return symbol.replace('/', '')


def fetch_price_df(symbol='ZEC/USDT', timeframe='1d', limit=365, since=None, max_retries=3) -> pd.DataFrame:
    """
    仅抓取并返回价格 DataFrame（不落盘）。
    - timestamp: 毫秒整数
    - datetime: pandas datetime（UTC）
    若抓取失败，返回合成 fallback 数据（同字段）。
    额外：在 df.attrs['source'] 标注 'binance' 或 'fallback'。
    """
    logger.info(f"Fetching {symbol} {timeframe} data from Binance (limit={limit})...")

    exchange = ccxt.binance({'enableRateLimit': True, 'options': {'adjustForTimeDifference': True}})

    # 配置代理（若环境变量存在）
    proxies = _get_proxies_from_env()
    if proxies:
        try:
            exchange.proxies = proxies
            exchange.session.proxies.update(proxies)
            logger.info("Using proxies: %s", proxies)
        except Exception as e:
            logger.warning("Failed to apply proxies to exchange session: %s", e)

    try:
        exchange.load_markets()
    except Exception as e:
        logger.warning("load_markets() failed: %s", e)

    attempt = 0
    ohlcv = None
    binance_hosts = [
        'api.binance.com',
        'api1.binance.com',
        'api2.binance.com',
        'api3.binance.com',
    ]
    base_index = 0

    while attempt < max_retries:
        try:
            _set_binance_base(exchange, binance_hosts[base_index % len(binance_hosts)])
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            break
        except ccxt.NetworkError as e:
            attempt += 1
            logger.warning("NetworkError fetching OHLCV (attempt %d/%d): %s", attempt, max_retries, e)
            base_index += 1
            time.sleep(1 + attempt * 2)
            continue
        except ccxt.ExchangeError as e:
            logger.error("ExchangeError fetching OHLCV: %s", e)
            raise
        except Exception as e:
            attempt += 1
            logger.exception("Unexpected error fetching OHLCV (attempt %d/%d): %s", attempt, max_retries, e)
            time.sleep(1 + attempt * 2)

    if not ohlcv:
        logger.error(f"Failed to fetch OHLCV for {symbol} after {max_retries} attempts; using fallback synthetic data.")
        df_fb = _generate_fallback_price_df(symbol, timeframe, limit)
        df_fb.attrs['source'] = 'fallback'
        return df_fb

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.attrs['source'] = 'binance'
    return df


def fetch_and_save_price(symbol='ZEC/USDT', timeframe='1d', limit=365, since=None, max_retries=3):
    """
    获取价格 DataFrame -> 保存到 RAW_DATA_DIR。
    返回 (filepath, is_fallback)
    """
    _ensure_raw_dir()
    df = fetch_price_df(symbol=symbol, timeframe=timeframe, limit=limit, since=since, max_retries=max_retries)
    is_fallback = (df.attrs.get('source') == 'fallback')

    safe_symbol = _safe_symbol(symbol)
    filename = f"price_{safe_symbol}_{timeframe}{'_fallback' if is_fallback else ''}.csv"
    filepath = RAW_DATA_DIR / filename
    df.to_csv(filepath, index=False)
    logger.info("Saved %d rows to %s (fallback=%s)", len(df), filepath, is_fallback)
    return str(filepath), is_fallback


def _generate_fallback_price_df(symbol, timeframe, limit) -> pd.DataFrame:
    """生成简单的合成价格 DataFrame，不保存。"""
    logger.info("Generating fallback synthetic price data for %s", symbol)
    end = datetime.utcnow()
    start = end - timedelta(days=limit - 1)
    dates = pd.date_range(start=start.date(), end=end.date(), freq='D')
    n = len(dates)

    price = 50.0
    opens, highs, lows, closes, volumes = [], [], [], [], []

    for _ in range(n):
        change = random.uniform(-0.05, 0.05)
        open_p = price
        close_p = max(0.001, price * (1 + change))
        high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.02))
        low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.02))
        vol = random.uniform(10, 1000)

        opens.append(open_p)
        highs.append(high_p)
        lows.append(low_p)
        closes.append(close_p)
        volumes.append(vol)

        price = close_p

    df = pd.DataFrame({
        'timestamp': (dates.astype(int) // 10**6).tolist(),  # ms
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes,
    })
    df['datetime'] = dates
    return df


def _generate_fallback_price(symbol, timeframe, limit):
    """兼容旧接口：生成合成数据并保存，返回文件路径。"""
    _ensure_raw_dir()
    safe_symbol = _safe_symbol(symbol)
    filename = f"price_{safe_symbol}_{timeframe}_fallback.csv"
    filepath = RAW_DATA_DIR / filename
    df = _generate_fallback_price_df(symbol, timeframe, limit)
    df.to_csv(filepath, index=False)
    logger.info("Saved fallback synthetic data to %s", filepath)
    return filepath


def load_price_df(symbol='ZEC/USDT', timeframe='1d') -> tuple[pd.DataFrame, bool]:
    """
    从 RAW_DATA_DIR 加载价格数据：
    - 优先加载真实数据文件 price_{symbol}_{timeframe}.csv
    - 不存在则加载 _fallback 版本
    - 若都不存在则调用 fetch_and_save_price 生成
    返回 (df, is_fallback)
    """
    _ensure_raw_dir()
    safe_symbol = _safe_symbol(symbol)
    main_path = RAW_DATA_DIR / f"price_{safe_symbol}_{timeframe}.csv"
    fb_path = RAW_DATA_DIR / f"price_{safe_symbol}_{timeframe}_fallback.csv"

    if main_path.exists():
        df = pd.read_csv(main_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        return df, False
    if fb_path.exists():
        df = pd.read_csv(fb_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        return df, True

    # 都不存在时，抓取并保存
    filepath, is_fallback = fetch_and_save_price(symbol=symbol, timeframe=timeframe)
    df = pd.read_csv(filepath)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df, is_fallback


if __name__ == "__main__":
    fetch_and_save_price()
