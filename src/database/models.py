"""
Database models for multi-symbol crypto attention analysis
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, Index, UniqueConstraint, create_engine, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime, timezone

Base = declarative_base()


class Symbol(Base):
    """加密货币标的表"""
    __tablename__ = 'symbols'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)  # e.g., 'ZEC', 'BTC'
    name = Column(String(100))  # e.g., 'Zcash', 'Bitcoin'
    aliases = Column(Text)  # 别名列表，逗号分隔，如 'Zcash,ZCash,z-cash' 用于新闻搜索
    coingecko_id = Column(String(100), index=True)  # CoinGecko ID，用于获取数据
    category = Column(String(50))  # e.g., 'privacy', 'defi', 'layer1'
    is_active = Column(Boolean, default=True)
    
    # 自动更新配置
    auto_update_price = Column(Boolean, default=False)  # 是否自动更新价格
    last_price_update = Column(DateTime(timezone=True))  # 最后一次价格更新时间
    last_attention_update = Column(DateTime(timezone=True))  # 最后一次特征值更新时间
    last_google_trends_update = Column(DateTime(timezone=True))  # 最后一次 Google Trends 更新时间
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    prices = relationship('Price', back_populates='symbol_ref', cascade='all, delete-orphan')
    attention_features = relationship('AttentionFeature', back_populates='symbol_ref', cascade='all, delete-orphan')
    google_trends = relationship('GoogleTrend', back_populates='symbol_ref', cascade='all, delete-orphan')
    twitter_volumes = relationship('TwitterVolume', back_populates='symbol_ref', cascade='all, delete-orphan')


class News(Base):
    """新闻数据表（所有币种共享）"""
    __tablename__ = 'news'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer, nullable=False, index=True)  # Unix timestamp (ms)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    title = Column(Text, nullable=False)
    source = Column(String(100), nullable=False, index=True)
    url = Column(Text, unique=True, nullable=False)
    language = Column(String(10))
    platform = Column(String(50))
    author = Column(String(200))
    node = Column(String(200))
    node_id = Column(String(255), index=True)
    
    # 关联字段（多对多：一条新闻可能涉及多个币种）
    symbols = Column(String(200))  # 逗号分隔的 symbol list, e.g., 'ZEC,BTC'
    relevance = Column(String(20))  # 'direct' or 'related'
    
    # 特征字段（从 news_features.py 计算）
    source_weight = Column(Float)
    sentiment_score = Column(Float)
    tags = Column(String(200))  # 逗号分隔的标签
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 索引优化
    __table_args__ = (
        Index('ix_news_datetime_symbols', 'datetime', 'symbols'),
        Index('ix_news_source_datetime', 'source', 'datetime'),
    )


class Price(Base):
    """价格 OHLCV 数据表"""
    __tablename__ = 'prices'
    
    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey('symbols.id'), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)  # '1d', '4h', '1h', etc.
    
    timestamp = Column(Integer, nullable=False)  # Unix timestamp (ms)
    datetime = Column(DateTime(timezone=True), nullable=False)
    
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    # 关系
    symbol_ref = relationship('Symbol', back_populates='prices')
    
    # 唯一约束：symbol + timeframe + datetime 唯一
    __table_args__ = (
        UniqueConstraint('symbol_id', 'timeframe', 'datetime', name='uq_price_symbol_tf_dt'),
        Index('ix_price_symbol_tf_datetime', 'symbol_id', 'timeframe', 'datetime'),
    )


class AttentionFeature(Base):
    """注意力特征聚合表（支持日级和 4H 级）"""
    __tablename__ = 'attention_features'
    
    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey('symbols.id'), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False)
    # 时间频率：'D' 为日级，'4H' 为 4 小时级
    timeframe = Column(String(10), nullable=False, default='D', index=True)
    
    # 基础特征
    news_count = Column(Integer, nullable=False, default=0)
    attention_score = Column(Float, nullable=False, default=0.0)  # 0-100
    
    # 扩展特征
    weighted_attention = Column(Float, default=0.0)
    bullish_attention = Column(Float, default=0.0)
    bearish_attention = Column(Float, default=0.0)
    event_intensity = Column(Integer, default=0)  # 0 or 1
    news_channel_score = Column(Float, default=0.0)
    google_trend_value = Column(Float, default=0.0)
    google_trend_zscore = Column(Float, default=0.0)
    google_trend_change_7d = Column(Float, default=0.0)
    google_trend_change_30d = Column(Float, default=0.0)
    twitter_volume = Column(Float, default=0.0)
    twitter_volume_zscore = Column(Float, default=0.0)
    twitter_volume_change_7d = Column(Float, default=0.0)
    composite_attention_score = Column(Float, default=0.0)
    composite_attention_zscore = Column(Float, default=0.0)
    composite_attention_spike_flag = Column(Integer, default=0)
    
    # 关系
    symbol_ref = relationship('Symbol', back_populates='attention_features')
    
    # 唯一约束：symbol + datetime + timeframe 唯一
    __table_args__ = (
        UniqueConstraint('symbol_id', 'datetime', 'timeframe', name='uq_attention_symbol_dt_tf'),
        Index('ix_attention_symbol_datetime_tf', 'symbol_id', 'datetime', 'timeframe'),
    )


class GoogleTrend(Base):
    """Google Trends time-series samples for each symbol."""

    __tablename__ = 'google_trends'

    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey('symbols.id'), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False)
    trend_value = Column(Float, nullable=False, default=0.0)
    keyword_set = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    symbol_ref = relationship('Symbol', back_populates='google_trends')

    __table_args__ = (
        UniqueConstraint('symbol_id', 'datetime', name='uq_google_trend_symbol_dt'),
        Index('ix_google_trend_symbol_datetime', 'symbol_id', 'datetime'),
    )


class TwitterVolume(Base):
    """Twitter volume time-series samples for each symbol."""

    __tablename__ = 'twitter_volumes'

    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey('symbols.id'), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False)
    tweet_count = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    symbol_ref = relationship('Symbol', back_populates='twitter_volumes')

    __table_args__ = (
        UniqueConstraint('symbol_id', 'datetime', name='uq_twitter_volume_symbol_dt'),
        Index('ix_twitter_volume_symbol_datetime', 'symbol_id', 'datetime'),
    )


class NodeAttentionFeature(Base):
    """节点级注意力特征表

    按 (symbol, node_id, datetime) 存储节点粒度的注意力特征，
    主要用于后续节点带货能力因子计算。
    """

    __tablename__ = 'node_attention_features'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    node_id = Column(String(200), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)

    freq = Column(String(10), nullable=False, default='D')

    news_count = Column(Integer, nullable=False, default=0)
    weighted_attention = Column(Float, default=0.0)
    bullish_attention = Column(Float, default=0.0)
    bearish_attention = Column(Float, default=0.0)
    sentiment_mean = Column(Float)
    sentiment_std = Column(Float)

    __table_args__ = (
        UniqueConstraint('symbol', 'node_id', 'datetime', name='uq_node_attention_symbol_node_dt'),
        Index('ix_node_attention_symbol_node_dt', 'symbol', 'node_id', 'datetime'),
    )

    @classmethod
    def from_record(cls, rec: dict) -> "NodeAttentionFeature":
        return cls(
            symbol=str(rec.get('symbol')),
            node_id=str(rec.get('node_id')),
            datetime=rec.get('datetime'),
            freq=str(rec.get('freq', 'D')),
            news_count=int(rec.get('news_count', 0)),
            weighted_attention=float(rec.get('weighted_attention', 0.0) or 0.0),
            bullish_attention=float(rec.get('bullish_attention', 0.0) or 0.0),
            bearish_attention=float(rec.get('bearish_attention', 0.0) or 0.0),
            sentiment_mean=float(rec.get('sentiment_mean')) if rec.get('sentiment_mean') is not None else None,
            sentiment_std=float(rec.get('sentiment_std')) if rec.get('sentiment_std') is not None else None,
        )


class NodeCarryFactorModel(Base):
    """节点带货能力因子表

    存储每个节点在给定 (symbol, lookahead, lookback) 条件下的统计表现。
    """

    __tablename__ = 'node_carry_factors'

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    node_id = Column(String(200), nullable=False, index=True)

    n_events = Column(Integer, nullable=False, default=0)
    mean_excess_return = Column(Float, nullable=False, default=0.0)
    hit_rate = Column(Float, nullable=False, default=0.0)
    ir = Column(Float, nullable=False, default=0.0)

    lookahead = Column(String(10), nullable=False, default='1d')
    lookback_days = Column(Integer, nullable=False, default=365)

    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('symbol', 'node_id', 'lookahead', 'lookback_days', name='uq_node_carry_key'),
        Index('ix_node_carry_symbol_node', 'symbol', 'node_id'),
    )

    @classmethod
    def from_record(cls, rec: dict) -> "NodeCarryFactorModel":
        return cls(
            symbol=str(rec.get('symbol')),
            node_id=str(rec.get('node_id')),
            n_events=int(rec.get('n_events', 0)),
            mean_excess_return=float(rec.get('mean_excess_return', 0.0) or 0.0),
            hit_rate=float(rec.get('hit_rate', 0.0) or 0.0),
            ir=float(rec.get('ir', 0.0) or 0.0),
            lookahead=str(rec.get('lookahead', '1d')),
            lookback_days=int(rec.get('lookback_days', 365)),
            updated_at=rec.get('updated_at') or datetime.now(timezone.utc),
        )


# 数据库引擎和会话工厂
def get_engine(db_url: str = None):
    """获取数据库引擎"""
    from src.config.settings import DATABASE_URL
    
    if db_url is None:
        db_url = DATABASE_URL
    
    # 根据数据库类型配置参数
    if db_url.startswith("sqlite"):
        # SQLite 专用配置
        engine = create_engine(
            db_url, 
            echo=False,
            connect_args={'timeout': 30}
        )
        # 启用 WAL 模式
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode=WAL;")
    else:
        # PostgreSQL / 其他数据库配置
        # pool_pre_ping=True 防止数据库连接断开
        engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        
    return engine


def init_database(db_url: str = None):
    """初始化数据库，创建所有表"""
    engine = get_engine(db_url)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine=None):
    """获取数据库会话"""
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
