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
    category = Column(String(50))  # e.g., 'privacy', 'defi', 'layer1'
    is_active = Column(Boolean, default=True)
    
    # 自动更新配置
    auto_update_price = Column(Boolean, default=False)  # 是否自动更新价格
    last_price_update = Column(DateTime(timezone=True))  # 最后一次价格更新时间
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    prices = relationship('Price', back_populates='symbol_ref', cascade='all, delete-orphan')
    attention_features = relationship('AttentionFeature', back_populates='symbol_ref', cascade='all, delete-orphan')


class News(Base):
    """新闻数据表（所有币种共享）"""
    __tablename__ = 'news'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer, nullable=False, index=True)  # Unix timestamp (ms)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    title = Column(Text, nullable=False)
    source = Column(String(100), nullable=False, index=True)
    url = Column(Text, unique=True, nullable=False)
    
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
    """注意力特征聚合表（每日）"""
    __tablename__ = 'attention_features'
    
    id = Column(Integer, primary_key=True)
    symbol_id = Column(Integer, ForeignKey('symbols.id'), nullable=False, index=True)
    datetime = Column(DateTime(timezone=True), nullable=False)
    
    # 基础特征
    news_count = Column(Integer, nullable=False, default=0)
    attention_score = Column(Float, nullable=False, default=0.0)  # 0-100
    
    # 扩展特征
    weighted_attention = Column(Float, default=0.0)
    bullish_attention = Column(Float, default=0.0)
    bearish_attention = Column(Float, default=0.0)
    event_intensity = Column(Integer, default=0)  # 0 or 1
    
    # 关系
    symbol_ref = relationship('Symbol', back_populates='attention_features')
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint('symbol_id', 'datetime', name='uq_attention_symbol_dt'),
        Index('ix_attention_symbol_datetime', 'symbol_id', 'datetime'),
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
