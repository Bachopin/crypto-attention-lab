"""
Database models for multi-symbol crypto attention analysis

支持 SQLite 和 PostgreSQL (with pgvector)
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, DateTime, Text, Boolean,
    ForeignKey, Index, UniqueConstraint, create_engine, func, Date
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime, timezone
import os

Base = declarative_base()

# 检查是否使用 PostgreSQL（用于条件启用 pgvector）
_DB_URL = os.getenv("DATABASE_URL", "")
IS_POSTGRESQL = _DB_URL.startswith("postgresql")

# pgvector 支持（仅 PostgreSQL）
if IS_POSTGRESQL:
    try:
        from pgvector.sqlalchemy import Vector
        VECTOR_ENABLED = True
    except ImportError:
        VECTOR_ENABLED = False
        Vector = None
else:
    VECTOR_ENABLED = False
    Vector = None


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
    
    # 预计算缓存字段
    event_performance_cache = Column(Text)  # JSON: 事件表现统计缓存
    event_performance_updated_at = Column(DateTime(timezone=True))  # 事件表现缓存更新时间
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    prices = relationship('Price', back_populates='symbol_ref', cascade='all, delete-orphan')
    attention_features = relationship('AttentionFeature', back_populates='symbol_ref', cascade='all, delete-orphan')
    google_trends = relationship('GoogleTrend', back_populates='symbol_ref', cascade='all, delete-orphan')
    twitter_volumes = relationship('TwitterVolume', back_populates='symbol_ref', cascade='all, delete-orphan')
    state_snapshots = relationship('StateSnapshot', back_populates='symbol_ref', cascade='all, delete-orphan')


class News(Base):
    """新闻数据表（所有币种共享）"""
    __tablename__ = 'news'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(BigInteger, nullable=False, index=True)  # Unix timestamp (ms)
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
    
    timestamp = Column(BigInteger, nullable=False)  # Unix timestamp (ms)
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
    """注意力特征聚合表（支持日级和 4H 级）
    
    这是核心的预计算特征表，包含：
    1. 注意力通道特征（新闻、Google Trends、Twitter）
    2. 价格派生特征（收益率、波动率、成交量 z-score）
    3. State Features（用于相似状态检索的规范化特征）
    4. Forward Returns（历史数据的前瞻收益，用于场景分析）
    5. Feature Vector（用于 pgvector 相似度搜索）
    """
    __tablename__ = 'attention_features'
    
    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey('symbols.id'), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False)
    # 时间频率：'D' 为日级，'4H' 为 4 小时级
    timeframe = Column(String(10), nullable=False, default='D', index=True)
    
    # ========== 基础注意力特征 ==========
    news_count = Column(Integer, nullable=False, default=0)
    attention_score = Column(Float, nullable=False, default=0.0)  # 0-100
    
    # 扩展注意力特征
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
    
    # 预计算的事件（JSON 格式）
    detected_events = Column(Text)  # JSON 字符串
    
    # ========== 新增: 价格快照 ==========
    close_price = Column(Float)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    volume = Column(Float)
    
    # ========== 新增: 滚动收益率 ==========
    return_1d = Column(Float)   # 1 天收益率
    return_7d = Column(Float)   # 7 天累计收益率
    return_30d = Column(Float)  # 30 天累计收益率
    return_60d = Column(Float)  # 60 天累计收益率
    
    # ========== 新增: 滚动波动率 ==========
    volatility_7d = Column(Float)   # 7 天波动率
    volatility_30d = Column(Float)  # 30 天波动率
    volatility_60d = Column(Float)  # 60 天波动率
    
    # ========== 新增: 其他滚动统计 ==========
    volume_zscore_7d = Column(Float)   # 7 天成交量 z-score
    volume_zscore_30d = Column(Float)  # 30 天成交量 z-score
    high_30d = Column(Float)   # 30 天最高价
    low_30d = Column(Float)    # 30 天最低价
    high_60d = Column(Float)   # 60 天最高价
    low_60d = Column(Float)    # 60 天最低价
    
    # ========== 新增: State Features (规范化，用于相似度检索) ==========
    # 收益动量 z-score
    feat_ret_zscore_7d = Column(Float)
    feat_ret_zscore_30d = Column(Float)
    feat_ret_zscore_60d = Column(Float)
    # 波动水平 z-score
    feat_vol_zscore_7d = Column(Float)
    feat_vol_zscore_30d = Column(Float)
    feat_vol_zscore_60d = Column(Float)
    # 注意力趋势
    feat_att_trend_7d = Column(Float)   # 7 天注意力斜率
    # 通道占比
    feat_att_news_share = Column(Float)
    feat_att_google_share = Column(Float)
    feat_att_twitter_share = Column(Float)
    # 情绪
    feat_bullish_minus_bearish = Column(Float)
    feat_sentiment_mean = Column(Float)
    
    # ========== 新增: Forward Returns (仅历史数据，T+N 后回填) ==========
    forward_return_3d = Column(Float)   # 3 天后收益
    forward_return_7d = Column(Float)   # 7 天后收益
    forward_return_30d = Column(Float)  # 30 天后收益
    max_drawdown_7d = Column(Float)     # 7 天内最大回撤
    max_drawdown_30d = Column(Float)    # 30 天内最大回撤
    
    # ========== 新增: Feature Vector (pgvector, 仅 PostgreSQL) ==========
    # 12 维特征向量，用于高效相似度搜索
    # 包含: [feat_ret_zscore_30d, feat_vol_zscore_30d, composite_attention_zscore,
    #        feat_att_trend_7d, feat_att_news_share, feat_att_google_share,
    #        feat_att_twitter_share, feat_bullish_minus_bearish, feat_sentiment_mean,
    #        volume_zscore_30d, google_trend_zscore, twitter_volume_zscore]
    # 注意: 此字段仅在 PostgreSQL + pgvector 环境下使用
    # feature_vector = Column(Vector(12))  # 需要 pgvector 扩展
    
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


class StateSnapshot(Base):
    """状态快照预计算表
    
    存储每个时间点的状态特征向量，避免实时计算开销。
    支持 1d 和 4h 两种时间粒度，固定 window_days=30。
    """
    
    __tablename__ = 'state_snapshots'
    
    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey('symbols.id'), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, default='1d', index=True)  # '1d' 或 '4h'
    window_days = Column(Integer, nullable=False, default=30)  # 固定为 30
    
    # 特征值 (JSON 存储)
    features = Column(Text, nullable=False)  # JSON: 标准化特征向量
    raw_stats = Column(Text)  # JSON: 原始统计数据
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    symbol_ref = relationship('Symbol', back_populates='state_snapshots')
    
    __table_args__ = (
        UniqueConstraint('symbol_id', 'datetime', 'timeframe', 'window_days', name='uq_state_snapshot_key'),
        Index('ix_state_snapshot_lookup', 'symbol_id', 'timeframe', 'datetime'),
    )
    
    @classmethod
    def from_computed(cls, symbol_id: int, dt: datetime, timeframe: str, 
                      features: dict, raw_stats: dict = None, window_days: int = 30):
        """从计算结果创建记录"""
        import json
        return cls(
            symbol_id=symbol_id,
            datetime=dt,
            timeframe=timeframe,
            window_days=window_days,
            features=json.dumps(features, ensure_ascii=False),
            raw_stats=json.dumps(raw_stats, ensure_ascii=False) if raw_stats else None,
        )
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        import json
        return {
            'datetime': self.datetime.isoformat() if self.datetime else None,
            'timeframe': self.timeframe,
            'window_days': self.window_days,
            'features': json.loads(self.features) if self.features else {},
            'raw_stats': json.loads(self.raw_stats) if self.raw_stats else {},
        }


class NewsStats(Base):
    """新闻统计缓存表
    
    存储预计算的新闻统计数据，避免每次 API 调用都全表扫描。
    
    stat_type:
    - 'total': 全局总数，period_key = 'ALL'
    - 'hourly': 每小时统计，period_key = '2025-12-01T14' (ISO日期+小时)
    - 'daily': 每日统计，period_key = '2025-12-01' (ISO日期)
    """
    __tablename__ = 'news_stats'
    
    id = Column(Integer, primary_key=True)
    stat_type = Column(String(20), nullable=False, index=True)  # 'total', 'hourly', 'daily'
    period_key = Column(String(20), nullable=False, index=True)  # 时间标识或 'ALL'
    count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('stat_type', 'period_key', name='uq_news_stats_type_period'),
        Index('ix_news_stats_type_period', 'stat_type', 'period_key'),
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
