"""
Database storage layer with backward compatibility
统一的数据存取接口，支持数据库和CSV双模式
"""
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List
import logging
from sqlalchemy import and_, or_, inspect, text

from src.config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR, DATA_DIR, NEWS_DATABASE_URL
from src.database.models import (
    Symbol, News, Price, AttentionFeature, GoogleTrend,
    init_database, get_session, get_engine
)

logger = logging.getLogger(__name__)

# 数据库模式标志
USE_DATABASE = True  # 设为 False 将回退到 CSV 模式
DISABLE_CSV_FALLBACK = os.getenv("DISABLE_CSV_FALLBACK", "false").lower() == "true"


class DatabaseStorage:
    """数据库存储后端"""
    
    def __init__(self):
        self.engine = init_database()
        # 初始化新闻数据库引擎
        self.news_engine = get_engine(NEWS_DATABASE_URL)
        # 确保新闻表在新闻数据库中存在
        News.__table__.create(bind=self.news_engine, checkfirst=True)
        self._ensure_news_columns()
        self._ensure_attention_columns()

    def _ensure_news_columns(self) -> None:
        columns = {
            "language": "TEXT",
            "platform": "TEXT",
            "author": "TEXT",
            "node": "TEXT",
            "node_id": "TEXT",
        }
        _ensure_columns(self.news_engine, 'news', columns)

    def _ensure_attention_columns(self) -> None:
        columns = {
            "google_trend_value": "FLOAT DEFAULT 0",
            "google_trend_zscore": "FLOAT DEFAULT 0",
            "google_trend_change_7d": "FLOAT DEFAULT 0",
            "google_trend_change_30d": "FLOAT DEFAULT 0",
            "twitter_volume": "FLOAT DEFAULT 0",
            "twitter_volume_zscore": "FLOAT DEFAULT 0",
            "twitter_volume_change_7d": "FLOAT DEFAULT 0",
            "news_channel_score": "FLOAT DEFAULT 0",
            "composite_attention_score": "FLOAT DEFAULT 0",
            "composite_attention_zscore": "FLOAT DEFAULT 0",
            "composite_attention_spike_flag": "INTEGER DEFAULT 0",
        }
        _ensure_columns(self.engine, 'attention_features', columns)
    
    def get_or_create_symbol(self, session, symbol: str, name: str = None, category: str = None) -> Symbol:
        """获取或创建币种记录"""
        sym = session.query(Symbol).filter_by(symbol=symbol.upper()).first()
        if not sym:
            sym = Symbol(
                symbol=symbol.upper(),
                name=name or symbol,
                category=category
            )
            session.add(sym)
            session.commit()
        return sym
    
    def save_news(self, news_records: List[dict]):
        """批量保存新闻（去重）"""
        if not news_records:
            return
            
        session = get_session(self.news_engine)
        try:
            # 优化：批量查询已存在的 URL
            urls = [r['url'] for r in news_records]
            existing_urls = set()
            
            # 分批查询以避免 SQL 语句过长
            chunk_size = 500
            for i in range(0, len(urls), chunk_size):
                chunk = urls[i:i+chunk_size]
                results = session.query(News.url).filter(News.url.in_(chunk)).all()
                existing_urls.update(r[0] for r in results)
            
            new_objects = []
            for record in news_records:
                if record['url'] in existing_urls:
                    continue
                
                # 本地去重（防止本次 batch 内重复）
                existing_urls.add(record['url'])
                
                news = News(
                    timestamp=record.get('timestamp', 0),
                    datetime=pd.to_datetime(record['datetime'], utc=True),
                    title=record['title'],
                    source=record['source'],
                    url=record['url'],
                    language=record.get('language'),
                    platform=record.get('platform'),
                    author=record.get('author'),
                    node=record.get('node'),
                    node_id=record.get('node_id'),
                    symbols=record.get('symbols', ''),
                    relevance=record.get('relevance', 'related'),
                    source_weight=record.get('source_weight'),
                    sentiment_score=record.get('sentiment_score'),
                    tags=record.get('tags', ''),
                )
                new_objects.append(news)
            
            if new_objects:
                session.bulk_save_objects(new_objects)
                session.commit()
                logger.info(f"Saved {len(new_objects)} new news items to separate news DB")
            else:
                logger.info("No new news items to save")
                
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save news: {e}")
            raise
        finally:
            session.close()
    
    def get_news(
        self,
        symbols: List[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """查询新闻数据"""
        session = get_session(self.news_engine)
        try:
            query = session.query(News)
            
            if symbols:
                # 支持多币种查询（OR 条件）
                symbol_filters = [News.symbols.contains(sym.upper()) for sym in symbols]
                query = query.filter(or_(*symbol_filters))
            
            if start:
                start_ts = start if isinstance(start, pd.Timestamp) else pd.Timestamp(start)
                if start_ts.tz is None:
                    start_ts = start_ts.tz_localize('UTC')
                query = query.filter(News.datetime >= start_ts)
            if end:
                end_ts = end if isinstance(end, pd.Timestamp) else pd.Timestamp(end)
                if end_ts.tz is None:
                    end_ts = end_ts.tz_localize('UTC')
                query = query.filter(News.datetime <= end_ts)
            
            query = query.order_by(News.datetime.desc())
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
            if not results:
                return pd.DataFrame()
            
            return pd.DataFrame([{
                'timestamp': n.timestamp,
                'datetime': n.datetime,
                'title': n.title,
                'source': n.source,
                'url': n.url,
                'language': n.language,
                'platform': n.platform,
                'author': n.author,
                'node': n.node,
                'node_id': n.node_id,
                'symbols': n.symbols,
                'relevance': n.relevance,
                'source_weight': n.source_weight,
                'sentiment_score': n.sentiment_score,
                'tags': n.tags,
            } for n in results])
        finally:
            session.close()
    
    def save_prices(self, symbol: str, timeframe: str, price_records: List[dict]):
        """批量保存价格数据"""
        session = get_session(self.engine)
        try:
            sym = self.get_or_create_symbol(session, symbol)
            
            for record in price_records:
                dt = pd.to_datetime(record['datetime'], utc=True)
                
                # 检查是否已存在
                existing = session.query(Price).filter(
                    and_(
                        Price.symbol_id == sym.id,
                        Price.timeframe == timeframe,
                        Price.datetime == dt
                    )
                ).first()
                
                if existing:
                    # 更新
                    existing.open = record['open']
                    existing.high = record['high']
                    existing.low = record['low']
                    existing.close = record['close']
                    existing.volume = record['volume']
                else:
                    # 新增
                    price = Price(
                        symbol_id=sym.id,
                        timeframe=timeframe,
                        timestamp=record.get('timestamp', int(dt.timestamp() * 1000)),
                        datetime=dt,
                        open=record['open'],
                        high=record['high'],
                        low=record['low'],
                        close=record['close'],
                        volume=record['volume'],
                    )
                    session.add(price)
            
            session.commit()
        finally:
            session.close()
    
    def get_prices(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """查询价格数据"""
        session = get_session(self.engine)
        try:
            sym = session.query(Symbol).filter_by(symbol=symbol.upper()).first()
            if not sym:
                return pd.DataFrame()
            
            query = session.query(Price).filter(
                and_(
                    Price.symbol_id == sym.id,
                    Price.timeframe == timeframe
                )
            )
            
            if start:
                start_ts = start if isinstance(start, pd.Timestamp) else pd.Timestamp(start)
                if start_ts.tz is None:
                    start_ts = start_ts.tz_localize('UTC')
                query = query.filter(Price.datetime >= start_ts)
            if end:
                end_ts = end if isinstance(end, pd.Timestamp) else pd.Timestamp(end)
                if end_ts.tz is None:
                    end_ts = end_ts.tz_localize('UTC')
                query = query.filter(Price.datetime <= end_ts)
            
            query = query.order_by(Price.datetime)
            
            results = query.all()
            if not results:
                return pd.DataFrame()
            
            return pd.DataFrame([{
                'timestamp': p.timestamp,
                'datetime': p.datetime,
                'open': p.open,
                'high': p.high,
                'low': p.low,
                'close': p.close,
                'volume': p.volume,
            } for p in results])
        finally:
            session.close()
    
    def save_attention_features(self, symbol: str, features: List[dict]):
        """保存注意力特征"""
        session = get_session(self.engine)
        try:
            sym = self.get_or_create_symbol(session, symbol)
            
            for record in features:
                dt = pd.to_datetime(record['datetime'], utc=True)
                
                existing = session.query(AttentionFeature).filter(
                    and_(
                        AttentionFeature.symbol_id == sym.id,
                        AttentionFeature.datetime == dt
                    )
                ).first()
                
                if existing:
                    # 更新
                    existing.news_count = record.get('news_count', 0)
                    existing.attention_score = record.get('attention_score', 0.0)
                    existing.weighted_attention = record.get('weighted_attention', 0.0)
                    existing.bullish_attention = record.get('bullish_attention', 0.0)
                    existing.bearish_attention = record.get('bearish_attention', 0.0)
                    existing.event_intensity = record.get('event_intensity', 0)
                    existing.news_channel_score = record.get('news_channel_score', 0.0)
                    existing.google_trend_value = record.get('google_trend_value', 0.0)
                    existing.google_trend_zscore = record.get('google_trend_zscore', 0.0)
                    existing.google_trend_change_7d = record.get('google_trend_change_7d', 0.0)
                    existing.google_trend_change_30d = record.get('google_trend_change_30d', 0.0)
                    existing.twitter_volume = record.get('twitter_volume', 0.0)
                    existing.twitter_volume_zscore = record.get('twitter_volume_zscore', 0.0)
                    existing.twitter_volume_change_7d = record.get('twitter_volume_change_7d', 0.0)
                    existing.composite_attention_score = record.get('composite_attention_score', 0.0)
                    existing.composite_attention_zscore = record.get('composite_attention_zscore', 0.0)
                    existing.composite_attention_spike_flag = record.get('composite_attention_spike_flag', 0)
                else:
                    feat = AttentionFeature(
                        symbol_id=sym.id,
                        datetime=dt,
                        news_count=record.get('news_count', 0),
                        attention_score=record.get('attention_score', 0.0),
                        weighted_attention=record.get('weighted_attention', 0.0),
                        bullish_attention=record.get('bullish_attention', 0.0),
                        bearish_attention=record.get('bearish_attention', 0.0),
                        event_intensity=record.get('event_intensity', 0),
                        news_channel_score=record.get('news_channel_score', 0.0),
                        google_trend_value=record.get('google_trend_value', 0.0),
                        google_trend_zscore=record.get('google_trend_zscore', 0.0),
                        google_trend_change_7d=record.get('google_trend_change_7d', 0.0),
                        google_trend_change_30d=record.get('google_trend_change_30d', 0.0),
                        twitter_volume=record.get('twitter_volume', 0.0),
                        twitter_volume_zscore=record.get('twitter_volume_zscore', 0.0),
                        twitter_volume_change_7d=record.get('twitter_volume_change_7d', 0.0),
                        composite_attention_score=record.get('composite_attention_score', 0.0),
                        composite_attention_zscore=record.get('composite_attention_zscore', 0.0),
                        composite_attention_spike_flag=record.get('composite_attention_spike_flag', 0),
                    )
                    session.add(feat)
            
            session.commit()
        finally:
            session.close()
    
    def get_attention_features(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """查询注意力特征"""
        session = get_session(self.engine)
        try:
            sym = session.query(Symbol).filter_by(symbol=symbol.upper()).first()
            if not sym:
                return pd.DataFrame()
            
            query = session.query(AttentionFeature).filter_by(symbol_id=sym.id)
            
            if start:
                start_ts = start if isinstance(start, pd.Timestamp) else pd.Timestamp(start)
                if start_ts.tz is None:
                    start_ts = start_ts.tz_localize('UTC')
                query = query.filter(AttentionFeature.datetime >= start_ts)
            if end:
                end_ts = end if isinstance(end, pd.Timestamp) else pd.Timestamp(end)
                if end_ts.tz is None:
                    end_ts = end_ts.tz_localize('UTC')
                query = query.filter(AttentionFeature.datetime <= end_ts)
            
            query = query.order_by(AttentionFeature.datetime)
            
            results = query.all()
            if not results:
                return pd.DataFrame()
            
            return pd.DataFrame([{
                'datetime': f.datetime,
                'news_count': f.news_count,
                'attention_score': f.attention_score,
                'weighted_attention': f.weighted_attention,
                'bullish_attention': f.bullish_attention,
                'bearish_attention': f.bearish_attention,
                'event_intensity': f.event_intensity,
                'news_channel_score': f.news_channel_score,
                'google_trend_value': f.google_trend_value,
                'google_trend_zscore': f.google_trend_zscore,
                'google_trend_change_7d': f.google_trend_change_7d,
                'google_trend_change_30d': f.google_trend_change_30d,
                'twitter_volume': f.twitter_volume,
                'twitter_volume_zscore': f.twitter_volume_zscore,
                'twitter_volume_change_7d': f.twitter_volume_change_7d,
                'composite_attention_score': f.composite_attention_score,
                'composite_attention_zscore': f.composite_attention_zscore,
                'composite_attention_spike_flag': f.composite_attention_spike_flag,
            } for f in results])
        finally:
            session.close()

    def save_google_trends(self, symbol: str, trends: List[dict]) -> None:
        """Persist Google Trends rows to the relational store."""

        if not trends:
            return

        session = get_session(self.engine)
        try:
            norm = symbol.upper()
            if norm.endswith('USDT'):
                norm = norm[:-4]
            if '/' in norm:
                norm = norm.split('/')[0]
            sym = self.get_or_create_symbol(session, norm)

            for record in trends:
                dt = record.get('datetime')
                if dt is None:
                    continue
                dt = pd.to_datetime(dt, utc=True, errors='coerce')
                if pd.isna(dt):
                    continue

                value = record.get('value', record.get('trend_value', 0.0))
                try:
                    value = float(value or 0.0)
                except (TypeError, ValueError):
                    value = 0.0

                keyword_set = record.get('keyword_set')

                existing = session.query(GoogleTrend).filter(
                    and_(
                        GoogleTrend.symbol_id == sym.id,
                        GoogleTrend.datetime == dt,
                    )
                ).first()

                if existing:
                    existing.trend_value = value
                    if keyword_set:
                        existing.keyword_set = keyword_set
                else:
                    gt = GoogleTrend(
                        symbol_id=sym.id,
                        datetime=dt,
                        trend_value=value,
                        keyword_set=keyword_set,
                    )
                    session.add(gt)

            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("Failed to save Google Trends rows for %s: %s", symbol, exc)
            raise
        finally:
            session.close()

    def get_google_trends(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """Load cached Google Trends rows for a symbol."""

        session = get_session(self.engine)
        try:
            norm = (symbol or '').upper()
            if norm.endswith('USDT'):
                norm = norm[:-4]
            if '/' in norm:
                norm = norm.split('/')[0]

            sym = session.query(Symbol).filter_by(symbol=norm).first()
            if not sym:
                return pd.DataFrame()

            query = session.query(GoogleTrend).filter(GoogleTrend.symbol_id == sym.id)
            if start:
                start_ts = start if isinstance(start, pd.Timestamp) else pd.Timestamp(start)
                if start_ts.tz is None:
                    start_ts = start_ts.tz_localize('UTC')
                query = query.filter(GoogleTrend.datetime >= start_ts)
            if end:
                end_ts = end if isinstance(end, pd.Timestamp) else pd.Timestamp(end)
                if end_ts.tz is None:
                    end_ts = end_ts.tz_localize('UTC')
                query = query.filter(GoogleTrend.datetime <= end_ts)

            query = query.order_by(GoogleTrend.datetime)
            rows = query.all()
            if not rows:
                return pd.DataFrame()

            return pd.DataFrame([
                {
                    'datetime': row.datetime,
                    'value': row.trend_value,
                    'keyword_set': row.keyword_set,
                }
                for row in rows
            ])
        finally:
            session.close()
    
    def get_all_symbols(self, active_only: bool = True) -> List[str]:
        """获取所有币种列表"""
        session = get_session(self.engine)
        try:
            query = session.query(Symbol)
            if active_only:
                query = query.filter_by(is_active=True)
            return [s.symbol for s in query.all()]
        finally:
            session.close()
    
    def close(self):
        """关闭会话"""
        # self.session.close()
        pass


# 全局数据库实例（延迟初始化）
_db_storage = None


def get_db() -> DatabaseStorage:
    """获取数据库存储实例"""
    global _db_storage
    if _db_storage is None:
        _db_storage = DatabaseStorage()
    return _db_storage


def _ensure_columns(engine, table_name: str, column_defs: dict) -> None:
    """Best-effort ALTER TABLE to add missing columns."""

    if engine is None:
        return

    inspector = inspect(engine)
    try:
        existing = {col['name'] for col in inspector.get_columns(table_name)}
    except Exception as exc:
        logger.warning("Failed to inspect table %s: %s", table_name, exc)
        return

    for col_name, ddl in column_defs.items():
        if col_name in existing:
            continue
        statement = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {ddl}"
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
            logger.info("Added missing column %s.%s", table_name, col_name)
        except Exception as exc:  # pragma: no cover - sqlite limitations
            logger.warning("Failed to add column %s.%s: %s", table_name, col_name, exc)


# ========== 向后兼容的接口函数 ==========

def load_price_data(
    symbol: str,
    timeframe: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
) -> Tuple[pd.DataFrame, bool]:
    """
    加载价格数据（兼容旧接口）
    数据库为唯一真实来源；仅当显式关闭数据库模式时才读取 CSV。
    """
    if USE_DATABASE:
        try:
            db = get_db()
            # 标准化 symbol 格式
            if symbol.endswith('USDT') and '/' not in symbol:
                base = symbol[:-4]
            else:
                base = symbol.split('/')[0] if '/' in symbol else symbol[:3]

            df = db.get_prices(base, timeframe, start, end)
            return df, False
        except Exception as e:
            logger.error(f"Database price query failed: {e}")
            return pd.DataFrame(), False

    if DISABLE_CSV_FALLBACK:
        logger.info("CSV price fallback disabled; returning empty frame")
        return pd.DataFrame(), False

    price_file = RAW_DATA_DIR / f"price_{symbol}_{timeframe}.csv"
    fallback_file = RAW_DATA_DIR / f"price_{symbol}_{timeframe}_fallback.csv"

    is_fallback = False

    if price_file.exists():
        df = pd.read_csv(price_file)
    elif fallback_file.exists():
        df = pd.read_csv(fallback_file)
        is_fallback = True
    else:
        logger.warning(f"Price data not found for {symbol} {timeframe}")
        return pd.DataFrame(), True

    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True, errors='coerce')

    if start is not None:
        start_ts = pd.Timestamp(start, tz='UTC') if not hasattr(start, 'tz') else start
        df = df[df['datetime'] >= start_ts]
    if end is not None:
        end_ts = pd.Timestamp(end, tz='UTC') if not hasattr(end, 'tz') else end
        df = df[df['datetime'] <= end_ts]

    return df, is_fallback


def load_attention_data(
    symbol: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
) -> pd.DataFrame:
    """
    加载注意力特征数据（兼容旧接口）
    数据默认仅使用数据库，CSV 仅在显式关闭数据库模式时启用。
    """
    if USE_DATABASE:
        try:
            db = get_db()
            df = db.get_attention_features(symbol, start, end)
            return df
        except Exception as e:
            logger.error(f"Database attention query failed: {e}")
            return pd.DataFrame()

    if DISABLE_CSV_FALLBACK:
        logger.info("CSV attention fallback disabled; returning empty frame")
        return pd.DataFrame()

    symbol_lower = symbol.lower()
    attention_file = PROCESSED_DATA_DIR / f"attention_features_{symbol_lower}.csv"

    if not attention_file.exists():
        logger.warning(f"Attention features not found for {symbol}")
        return pd.DataFrame()

    df = pd.read_csv(attention_file)

    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True, errors='coerce')

    if start is not None:
        start_ts = pd.Timestamp(start, tz='UTC') if not hasattr(start, 'tz') else start
        df = df[df['datetime'] >= start_ts]
    if end is not None:
        end_ts = pd.Timestamp(end, tz='UTC') if not hasattr(end, 'tz') else end
        df = df[df['datetime'] <= end_ts]

    required_cols = [
        'news_channel_score',
        'google_trend_value',
        'google_trend_zscore',
        'google_trend_change_7d',
        'google_trend_change_30d',
        'twitter_volume',
        'twitter_volume_zscore',
        'twitter_volume_change_7d',
        'composite_attention_score',
        'composite_attention_zscore',
        'composite_attention_spike_flag',
    ]
    for col in required_cols:
        if col not in df.columns:
            default = 0.0 if not col.endswith('_flag') else 0
            df[col] = default

    return df


def load_news_data(
    symbol: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: Optional[int] = None
) -> pd.DataFrame:
    """
    加载新闻数据（兼容旧接口）
    支持多币种查询（传入逗号分隔的 symbols）
    传入 "ALL" 或空字符串则返回所有新闻
    """
    if USE_DATABASE:
        try:
            db = get_db()
            if not symbol or symbol.upper() == "ALL":
                symbols = None
            else:
                symbols = [s.strip() for s in symbol.split(',')]

            df = db.get_news(symbols, start, end, limit)
            return df
        except Exception as e:
            logger.error(f"Database news query failed: {e}")
            return pd.DataFrame()

    if DISABLE_CSV_FALLBACK:
        logger.info("CSV news fallback disabled; returning empty frame")
        return pd.DataFrame()

    symbol_lower = symbol.lower() if symbol else "all"
    news_file = RAW_DATA_DIR / f"attention_{symbol_lower}_news.csv"
    mock_file = RAW_DATA_DIR / f"attention_{symbol_lower}_mock.csv"

    if news_file.exists():
        df = pd.read_csv(news_file)
    elif mock_file.exists():
        df = pd.read_csv(mock_file)
    else:
        logger.warning(f"News data not found for {symbol}")
        return pd.DataFrame()

    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'], utc=True, errors='coerce')

    if start is not None:
        start_ts = pd.Timestamp(start, tz='UTC') if not hasattr(start, 'tz') else start
        df = df[df['datetime'] >= start_ts]
    if end is not None:
        end_ts = pd.Timestamp(end, tz='UTC') if not hasattr(end, 'tz') else end
        df = df[df['datetime'] <= end_ts]

    if limit:
        df = df.head(limit)

    return df


def ensure_price_data_exists(symbol: str, timeframe: str) -> bool:
    """
    确保价格数据存在（数据库优先模式）
    """
    if USE_DATABASE:
        # 仅检查数据库，不再自动获取CSV
        db = get_db()
        base_symbol = symbol[:-4] if symbol.endswith('USDT') else symbol.split('/')[0]
        df = db.get_prices(base_symbol, timeframe)
        return not df.empty
    
    # CSV fallback模式（仅当 USE_DATABASE=False 时）
    price_file = RAW_DATA_DIR / f"price_{symbol}_{timeframe}.csv"
    fallback_file = RAW_DATA_DIR / f"price_{symbol}_{timeframe}_fallback.csv"
    return price_file.exists() or fallback_file.exists()


def ensure_attention_data_exists(symbol: str) -> bool:
    """
    确保注意力数据存在（数据库优先模式）
    """
    if USE_DATABASE:
        # 仅检查数据库，不再自动生成CSV
        db = get_db()
        df = db.get_attention_features(symbol)
        return not df.empty
    
    # CSV fallback模式（仅当 USE_DATABASE=False 时）
    symbol_lower = symbol.lower()
    attention_file = PROCESSED_DATA_DIR / f"attention_features_{symbol_lower}.csv"
    return attention_file.exists()


def get_available_symbols() -> List[str]:
    """获取所有可用币种列表"""
    if USE_DATABASE:
        try:
            db = get_db()
            return db.get_all_symbols()
        except:
            pass
    
    # CSV fallback：扫描文件
    symbols = set()
    for f in RAW_DATA_DIR.glob("price_*_1d.csv"):
        name = f.stem.replace("price_", "").replace("_1d", "")
        if name.endswith("USDT"):
            symbols.add(name[:-4])
    
    return sorted(list(symbols))


# ==================== Convenience Wrappers ====================
# 为脚本提供简化的包装函数

def save_price_data(symbol: str, timeframe: str, price_records: List[dict]) -> int:
    """
    保存价格数据的便捷包装器
    Returns: 保存的记录数
    """
    if USE_DATABASE:
        db = get_db()
        db.save_prices(symbol, timeframe, price_records)
        return len(price_records)
    return 0
