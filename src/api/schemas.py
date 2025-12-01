from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union, Dict, Any
from enum import Enum
from datetime import datetime

# ==================== Enums ====================

class Timeframe(str, Enum):
    DAILY = "1d"
    FOUR_HOUR = "4h"
    ONE_HOUR = "1h"
    FIFTEEN_MIN = "15m"

class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"

class AttentionSource(str, Enum):
    LEGACY = "legacy"
    COMPOSITE = "composite"
    NEWS_CHANNEL = "news_channel"
    GOOGLE_CHANNEL = "google_channel"
    TWITTER_CHANNEL = "twitter_channel"

# ==================== Common Models ====================

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None

class DateRangeParams(BaseModel):
    start: Optional[str] = Field(None, description="ISO8601 start date")
    end: Optional[str] = Field(None, description="ISO8601 end date")

# ==================== Research Models ====================

class AttentionRegimeParams(BaseModel):
    symbols: List[str] = Field(..., min_length=1)
    lookahead_days: List[int] = Field(default=[7, 30])
    split_quantiles: Optional[List[float]] = None
    attention_source: AttentionSource = AttentionSource.COMPOSITE
    split_method: str = "tercile"
    start: Optional[str] = None
    end: Optional[str] = None

class StateSnapshotBatchParams(BaseModel):
    symbols: List[str] = Field(..., min_length=1)
    timeframe: Timeframe = Timeframe.DAILY
    window_days: int = Field(30, ge=7, le=365)

class SimilarCasesCustomParams(BaseModel):
    symbol: str
    timeframe: Timeframe = Timeframe.DAILY
    window_days: int = Field(30, ge=7, le=365)
    top_k: int = Field(50, ge=1, le=500)
    max_history_days: int = Field(365, ge=30, le=1095)
    distance_metric: str = "euclidean"
    include_same_symbol: bool = True
    exclusion_days: int = Field(7, ge=0)
    candidate_symbols: Optional[List[str]] = None

class ScenarioAnalysisCustomParams(BaseModel):
    symbol: str
    timeframe: Timeframe = Timeframe.DAILY
    window_days: int = Field(30, ge=7, le=365)
    top_k: int = Field(100, ge=10, le=500)
    max_history_days: int = Field(365, ge=30, le=1095)
    include_sample_details: bool = False
    lookahead_days: List[int] = Field(default=[3, 7, 30])
    candidate_symbols: Optional[List[str]] = None

# ==================== Backtest Models ====================

class AttentionRotationParams(BaseModel):
    symbols: List[str] = Field(..., min_length=1)
    attention_source: AttentionSource = AttentionSource.COMPOSITE
    rebalance_days: int = Field(7, ge=1)
    lookback_days: int = Field(30, ge=1)
    top_k: int = Field(3, ge=1)
    start: Optional[str] = None
    end: Optional[str] = None

class BacktestParams(BaseModel):
    """基础回测参数模型"""
    symbol: str = Field(..., description="交易对符号")
    lookback_days: int = Field(30, ge=1, description="回溯天数")
    attention_quantile: float = Field(0.8, ge=0.0, le=1.0, description="注意力分位数阈值")
    max_daily_return: float = Field(0.05, description="最大日涨幅限制")
    holding_days: int = Field(3, ge=1, description="持仓天数")
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    max_holding_days: Optional[int] = None
    position_size: float = Field(1.0, gt=0.0, le=1.0)
    start: Optional[str] = None
    end: Optional[str] = None
    attention_condition: Optional[Dict[str, Any]] = None
    attention_source: str = Field("legacy", pattern="^(legacy|composite)$")

class MultiBacktestParams(BacktestParams):
    """多币种回测参数模型"""
    symbol: Optional[str] = None # 覆盖父类，使其可选
    symbols: List[str] = Field(..., min_length=1, description="交易对列表")
