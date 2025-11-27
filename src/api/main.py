"""
Crypto Attention Lab - FastAPI Backend
提供价格、注意力和新闻数据的 REST API
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi import Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
import pandas as pd
import logging

from src.data.storage import (
    load_price_data,
    load_attention_data,
    load_news_data,
    ensure_price_data_exists,
    ensure_attention_data_exists
)
from src.utils.logger import setup_logging
from src.events.attention_events import detect_attention_events
from src.backtest.basic_attention_factor import run_backtest_basic_attention

# 设置日志
setup_logging(logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Crypto Attention Lab API",
    description="API for cryptocurrency attention analysis and price data",
    version="0.1.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境全开放，生产环境需要收紧
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 健康检查 ====================

@app.get("/health")
@app.get("/ping")
def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "Crypto Attention Lab API",
        "version": "0.1.0"
    }


# ==================== 价格数据 API ====================

@app.get("/api/price")
def get_price_data(
    symbol: str = Query(default="ZECUSDT", description="交易对符号，如 ZECUSDT"),
    timeframe: str = Query(default="1d", description="时间周期: 1d, 4h, 1h, 15m, 5m, 1m"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式")
):
    """
    获取价格 OHLCV 数据
    
    返回格式:
    [
        {
            "timestamp": 1700000000000,
            "datetime": "2025-11-26T00:00:00Z",
            "open": 500.0,
            "high": 520.0,
            "low": 495.0,
            "close": 510.0,
            "volume": 12345.67
        }
    ]
    """
    try:
        # 验证 timeframe
        valid_timeframes = ["1d", "4h", "1h", "15m", "5m", "1m"]
        if timeframe not in valid_timeframes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}"
            )
        
        # 解析时间参数
        start_dt = None
        end_dt = None
        
        if start:
            try:
                start_dt = pd.to_datetime(start, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        # 确保数据存在
        if not ensure_price_data_exists(symbol, timeframe):
            raise HTTPException(
                status_code=404,
                detail=f"Price data not available for {symbol} {timeframe}"
            )
        
        # 加载数据
        df, is_fallback = load_price_data(symbol, timeframe, start_dt, end_dt)
        
        if df.empty:
            return []
        
        # 转换为 API 响应格式
        result = []
        for _, row in df.iterrows():
            # 确保 datetime 是 pandas Timestamp
            dt = pd.to_datetime(row['datetime'])
            
            result.append({
                "timestamp": int(dt.timestamp() * 1000),  # 转为毫秒
                "datetime": dt.isoformat(),
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
                "volume": float(row.get('volume', 0))
            })
        
        logger.info(f"Returned {len(result)} price records for {symbol} {timeframe}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_price_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 注意力数据 API ====================

@app.get("/api/attention")
def get_attention_data(
    symbol: str = Query(default="ZEC", description="标的符号，如 ZEC"),
    granularity: str = Query(default="1d", description="时间粒度，目前仅支持 1d"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式")
):
    """
    获取注意力时间序列数据
    
    返回格式:
    [
        {
            "timestamp": 1700000000000,
            "datetime": "2025-11-26T00:00:00Z",
            "attention_score": 80.0,
            "news_count": 4
        }
    ]
    """
    try:
        # 解析时间参数
        start_dt = None
        end_dt = None
        
        if start:
            try:
                start_dt = pd.to_datetime(start, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        # 确保数据存在
        if not ensure_attention_data_exists(symbol):
            raise HTTPException(
                status_code=404,
                detail=f"Attention data not available for {symbol}"
            )
        
        # 加载数据
        df = load_attention_data(symbol, start_dt, end_dt)
        
        if df.empty:
            return []
        
        # 转换为 API 响应格式
        result = []
        for _, row in df.iterrows():
            dt = pd.to_datetime(row['datetime'])
            
            result.append({
                "timestamp": int(dt.timestamp() * 1000),
                "datetime": dt.isoformat(),
                "attention_score": float(row.get('attention_score', 0)),
                "news_count": int(row.get('news_count', 0)),
                "weighted_attention": float(row.get('weighted_attention', 0) or 0),
                "bullish_attention": float(row.get('bullish_attention', 0) or 0),
                "bearish_attention": float(row.get('bearish_attention', 0) or 0),
                "event_intensity": int(row.get('event_intensity', 0) or 0),
            })
        
        logger.info(f"Returned {len(result)} attention records for {symbol}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_attention_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 新闻数据 API ====================

@app.get("/api/news")
def get_news_data(
    symbol: str = Query(default="ZEC", description="标的符号，如 ZEC"),
    start: Optional[str] = Query(default=None, description="开始时间 ISO8601 格式"),
    end: Optional[str] = Query(default=None, description="结束时间 ISO8601 格式")
):
    """
    获取新闻列表
    
    返回格式:
    [
        {
            "datetime": "2025-11-26T23:38:17Z",
            "source": "CoinDesk",
            "title": "ZEC News Sample 8884",
            "url": "https://example.com/news/xxx"
        }
    ]
    """
    try:
        # 解析时间参数
        start_dt = None
        end_dt = None
        
        if start:
            try:
                start_dt = pd.to_datetime(start, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid start time format: {e}")
        
        if end:
            try:
                end_dt = pd.to_datetime(end, utc=True)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid end time format: {e}")
        
        # 加载新闻数据
        df = load_news_data(symbol, start_dt, end_dt)
        
        if df.empty:
            return []
        
        # 转换为 API 响应格式
        result = []
        for _, row in df.iterrows():
            dt = pd.to_datetime(row['datetime'])
            
            result.append({
                "datetime": dt.isoformat() if pd.notna(dt) else None,
                "source": str(row.get('source', 'Unknown')),
                "title": str(row.get('title', '')),
                "url": str(row.get('url', '')),
                "relevance": str(row.get('relevance', '')),
                "source_weight": float(row.get('source_weight', 0) or 0),
                "sentiment_score": float(row.get('sentiment_score', 0) or 0),
                "tags": str(row.get('tags', '')),
            })
        
        logger.info(f"Returned {len(result)} news items for {symbol}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_news_data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 根路径 ====================

@app.get("/")
def root():
    """API 根路径"""
    return {
        "message": "Crypto Attention Lab API",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health or /ping",
            "price": "/api/price?symbol=ZECUSDT&timeframe=1d",
            "attention": "/api/attention?symbol=ZEC",
            "news": "/api/news?symbol=ZEC",
            "update_data": "/api/update-data (POST)"
        },
        "docs": "/docs"
    }


# ==================== 数据更新 ====================

@app.post("/api/update-data")
def update_data(
    update_price: bool = Query(True, description="更新价格数据"),
    update_attention: bool = Query(True, description="更新注意力数据"),
    update_news: bool = Query(True, description="更新新闻数据")
):
    """
    手动触发数据更新

    - update_price: 是否更新价格数据
    - update_attention: 是否更新注意力数据
    - update_news: 是否更新新闻数据
    """
    import subprocess
    from pathlib import Path

    results = {
        "status": "success",
        "updated": []
    }

    project_root = Path(__file__).parent.parent.parent
    python_exe = "/Users/mextrel/VSCode/.venv/bin/python"

    try:
        if update_price:
            logger.info("Updating price data...")
            script_path = project_root / "scripts" / "fetch_price_data.py"
            result = subprocess.run(
                [python_exe, str(script_path)],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                results["updated"].append("price")
                logger.info("Price data updated successfully")
            else:
                logger.error(f"Failed to update price data: {result.stderr}")
                results["status"] = "partial"
                results["error_price"] = result.stderr

        if update_attention:
            logger.info("Updating attention data...")
            script_path = project_root / "scripts" / "generate_attention_data.py"
            result = subprocess.run(
                [python_exe, str(script_path)],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                results["updated"].append("attention")
                logger.info("Attention data updated successfully")
            else:
                logger.error(f"Failed to update attention data: {result.stderr}")
                results["status"] = "partial"
                results["error_attention"] = result.stderr

        # Update news data
        if update_news:
            logger.info("Updating news data...")
            script_path = project_root / "scripts" / "fetch_news_data.py"
            result = subprocess.run(
                [python_exe, str(script_path)],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                results["updated"].append("news")
                logger.info("News data updated successfully")
                
                # Regenerate attention features after news update
                logger.info("Regenerating attention features...")
                attention_script = project_root / "scripts" / "generate_attention_data.py"
                subprocess.run(
                    [python_exe, str(attention_script)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if "attention" not in results["updated"]:
                    results["updated"].append("attention")
            
            else:
                logger.error(f"Failed to update news data: {result.stderr}")
                results["status"] = "partial"
                results["error_news"] = result.stderr

        return results

    except Exception as e:
        logger.error(f"Error updating data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ==================== 注意力事件 API ====================

@app.get("/api/attention-events")
def get_attention_events(
    symbol: str = Query(default="ZEC"),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
    lookback_days: int = Query(default=30),
    min_quantile: float = Query(default=0.8),
):
    try:
        start_dt = pd.to_datetime(start, utc=True) if start else None
        end_dt = pd.to_datetime(end, utc=True) if end else None
        events = detect_attention_events(symbol=symbol, start=start_dt, end=end_dt, lookback_days=lookback_days, min_quantile=min_quantile)
        return [
            {
                "datetime": e.datetime.isoformat(),
                "event_type": e.event_type,
                "intensity": e.intensity,
                "summary": e.summary,
            } for e in events
        ]
    except Exception as e:
        logger.error(f"Error in get_attention_events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 基础回测 API ====================

@app.post("/api/backtest/basic-attention")
def backtest_basic_attention(
    payload: dict = Body(...)
):
    try:
        symbol = payload.get("symbol", "ZECUSDT")
        lookback_days = int(payload.get("lookback_days", 30))
        attention_quantile = float(payload.get("attention_quantile", 0.8))
        max_daily_return = float(payload.get("max_daily_return", 0.05))
        holding_days = int(payload.get("holding_days", 3))
        start = pd.to_datetime(payload.get("start"), utc=True) if payload.get("start") else None
        end = pd.to_datetime(payload.get("end"), utc=True) if payload.get("end") else None
        res = run_backtest_basic_attention(
            symbol=symbol,
            lookback_days=lookback_days,
            attention_quantile=attention_quantile,
            max_daily_return=max_daily_return,
            holding_days=holding_days,
            start=start,
            end=end,
        )
        return res
    except Exception as e:
        logger.error(f"Error in backtest_basic_attention: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
