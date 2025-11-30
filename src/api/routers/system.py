from fastapi import APIRouter, Body, Query, HTTPException
from typing import Optional, List, Dict, Any
import logging
import asyncio
import requests
import pandas as pd

from src.database.models import Symbol, get_session
from src.data.db_storage import get_db, load_price_data
from src.data.realtime_price_updater import get_realtime_updater, RealtimePriceUpdater
from src.services.attention_service import AttentionService

logger = logging.getLogger(__name__)

router = APIRouter()

# ==================== 自动更新管理 API ====================

@router.get("/api/auto-update/status", tags=["System"])
def get_auto_update_status():
    """
    获取所有标的的自动更新状态
    """
    try:
        session = get_session()
        # 显示：auto_update=True 或 曾经更新过价格（last_price_update 不为空）的代币
        # 这样暂停后的代币仍然会显示在列表中
        from sqlalchemy import or_
        symbols = session.query(Symbol).filter(
            or_(
                Symbol.auto_update_price == True,
                Symbol.last_price_update.isnot(None)
            )
        ).all()
        
        result = [{
            "symbol": s.symbol,
            "auto_update": s.auto_update_price,
            "last_update": s.last_price_update.isoformat() if s.last_price_update else None,
            "is_active": s.is_active
        } for s in symbols]
        
        session.close()
        return {"symbols": result}
        
    except Exception as e:
        logger.error(f"Error getting auto-update status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/auto-update/enable", tags=["System"])
async def enable_auto_update(
    payload: dict = Body(...)
):
    """
    启用标的的自动更新
    """
    try:
        symbols = payload.get("symbols", [])
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        db = get_db()
        session = get_session()
        enabled = []
        invalid = []
        
        for symbol_name in symbols:
            symbol_name = symbol_name.upper()
            
            # 验证交易对在 Binance 上是否存在（现货或合约）
            symbol_valid = False
            market_type = None
            
            # 先检查现货
            try:
                spot_url = f"https://api.binance.com/api/v3/klines?symbol={symbol_name}USDT&interval=1d&limit=1"
                # 使用 asyncio.to_thread 避免阻塞事件循环
                resp = await asyncio.to_thread(requests.get, spot_url, timeout=5)
                if resp.status_code == 200 and resp.json():
                    symbol_valid = True
                    market_type = "Spot"
            except:
                pass
            
            # 如果现货不存在，检查合约
            if not symbol_valid:
                try:
                    futures_url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol_name}USDT&interval=1d&limit=1"
                    resp = await asyncio.to_thread(requests.get, futures_url, timeout=5)
                    if resp.status_code == 200 and resp.json():
                        symbol_valid = True
                        market_type = "Futures"
                except:
                    pass
            
            if not symbol_valid:
                logger.warning(f"[Enable] {symbol_name}USDT not found on Binance (Spot or Futures)")
                invalid.append(symbol_name)
                continue
            
            logger.info(f"[Enable] {symbol_name}USDT found on Binance {market_type}")
            
            # 获取或创建 Symbol 记录
            sym = db.get_or_create_symbol(session, symbol_name)
            
            # 启用自动更新
            sym.auto_update_price = True
            sym.is_active = True
            enabled.append(symbol_name)
        
        session.commit()
        session.close()
        
        if invalid:
            logger.warning(f"Invalid symbols (not on Binance): {invalid}")
        
        if not enabled:
            raise HTTPException(
                status_code=400, 
                detail=f"No valid symbols to enable. Invalid: {invalid}"
            )
        
        logger.info(f"Enabled auto-update for: {enabled}")
        
        # 触发初始数据更新和 attention 计算
        updater = get_realtime_updater()
        initialized = []
        
        for symbol_name in enabled:
            try:
                logger.info(f"[Initialize] Starting initialization for {symbol_name}...")
                
                # 1. 检查是否有价格数据
                price_data = load_price_data(symbol_name, timeframe='1d')
                if isinstance(price_data, tuple):
                    df, _ = price_data
                else:
                    df = price_data
                
                needs_price_fetch = df is None or df.empty
                
                # 如果没有数据或数据过旧（超过7天），拉取历史数据
                if not needs_price_fetch and not df.empty:
                    last_date = pd.to_datetime(df['datetime']).max()
                    # 确保时区一致进行比较
                    if last_date.tzinfo is None:
                        last_date = last_date.tz_localize('UTC')
                    days_old = (pd.Timestamp.now(tz='UTC') - last_date).days
                    if days_old > 7:
                        needs_price_fetch = True
                        logger.info(f"[Initialize] {symbol_name} price data is {days_old} days old, will refresh")
                
                # 2. 拉取价格数据（如果需要）
                if needs_price_fetch:
                    logger.info(f"[Initialize] Fetching historical prices for {symbol_name} (≥1 year)...")
                    await updater.update_single_symbol(symbol_name, last_update=None)
                else:
                    logger.info(f"[Initialize] {symbol_name} has recent price data, skipping fetch")
                
                # 3. 计算 Attention Features
                logger.info(f"[Initialize] Calculating attention features for {symbol_name}...")
                await asyncio.to_thread(AttentionService.update_attention_features, symbol_name, freq='D', save_to_db=True)
                
                initialized.append(symbol_name)
                logger.info(f"[Initialize] ✅ {symbol_name} initialization completed")
                
            except Exception as e:
                logger.error(f"[Initialize] ❌ Failed to initialize {symbol_name}: {e}", exc_info=True)
                # 继续处理其他 symbol，不中断整个流程
        
        return {
            "status": "success",
            "enabled": enabled,
            "invalid": invalid,
            "initialized": initialized,
            "message": f"Enabled and initialized {len(initialized)}/{len(enabled)} symbols" + (f". Invalid symbols: {invalid}" if invalid else "")
        }
        
    except Exception as e:
        logger.error(f"Error enabling auto-update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/auto-update/disable", tags=["System"])
def disable_auto_update(
    payload: dict = Body(...)
):
    """
    禁用标的的自动更新
    """
    try:
        symbols = payload.get("symbols", [])
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        session = get_session()
        disabled = []
        
        for symbol_name in symbols:
            symbol_name = symbol_name.upper()
            sym = session.query(Symbol).filter_by(symbol=symbol_name).first()
            
            if sym:
                sym.auto_update_price = False
                sym.is_active = False
                disabled.append(symbol_name)
        
        session.commit()
        session.close()
        
        logger.info(f"Disabled auto-update for: {disabled}")
        return {
            "status": "success",
            "disabled": disabled
        }
        
    except Exception as e:
        logger.error(f"Error disabling auto-update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/auto-update/trigger", tags=["System"])
async def trigger_manual_update(
    payload: dict = Body(...)
):
    """
    手动触发指定标的的价格更新
    """
    try:
        symbols = payload.get("symbols", [])
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        
        updater = get_realtime_updater()
        session = get_session()
        
        updated = []
        for symbol_name in symbols:
            symbol_name = symbol_name.upper()
            sym = session.query(Symbol).filter_by(symbol=symbol_name).first()
            
            last_update = sym.last_price_update if sym else None
            
            # 执行更新
            await updater.update_single_symbol(symbol_name, last_update)
            updated.append(symbol_name)
        
        session.close()
        
        return {
            "status": "success",
            "updated": updated
        }
        
    except Exception as e:
        logger.error(f"Error triggering manual update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/attention/trigger-update", tags=["System"])
async def trigger_attention_update(
    payload: dict = Body(...)
):
    """
    手动触发指定标的的 Attention Features 更新
    """
    try:
        symbols = payload.get("symbols", [])
        freq = payload.get("freq", "D")
        
        # 如果没有指定 symbols，获取所有启用自动更新的代币
        if not symbols:
            session = get_session()
            enabled_symbols = session.query(Symbol).filter(
                Symbol.auto_update_price == True
            ).all()
            symbols = [s.symbol for s in enabled_symbols]
            session.close()
            
            if not symbols:
                return {
                    "status": "warning",
                    "updated": [],
                    "message": "No symbols enabled for auto-update"
                }
        
        updated = []
        errors = []
        
        for symbol_name in symbols:
            symbol_name = symbol_name.upper()
            try:
                logger.info(f"Manually triggering attention update for {symbol_name} (freq={freq})...")
                
                # 在线程池中运行同步函数，避免阻塞
                await asyncio.to_thread(AttentionService.update_attention_features, symbol_name, freq=freq)
                
                updated.append(symbol_name)
                logger.info(f"✅ Attention features updated for {symbol_name}")
                
            except Exception as e:
                error_msg = f"{symbol_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ Failed to update attention for {symbol_name}: {e}")
        
        response = {
            "status": "success" if updated else "error",
            "updated": updated,
            "message": f"Updated {len(updated)} symbol(s)"
        }
        
        if errors:
            response["errors"] = errors
            response["message"] += f", {len(errors)} failed"
        
        return response
        
    except Exception as e:
        logger.error(f"Error triggering attention update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/refresh-symbol", tags=["System"])
async def refresh_symbol(
    symbol: str = Query(..., description="要刷新的代币符号，如 BTC, ETH, HYPE"),
    check_completeness: bool = Query(True, description="是否检查数据完整性并自动补全缺失数据")
):
    """
    手动刷新单个代币的数据（价格 + Attention）
    """
    symbol = symbol.upper()
    logger.info(f"[Refresh] Manual refresh triggered for {symbol} (check_completeness={check_completeness})")
    
    results = {
        "status": "success",
        "symbol": symbol,
        "updated": [],
        "details": {}
    }
    
    try:
        # 获取 last_update 信息
        session = get_session()
        try:
            sym = session.query(Symbol).filter_by(symbol=symbol).first()
            last_update = sym.last_price_update if sym else None
        finally:
            session.close()
        
        # 创建更新器
        updater = RealtimePriceUpdater()
        
        # 手动刷新时：如果 check_completeness=True，强制检查每个 timeframe 的完整性
        # 这样可以自动补全缺失的历史数据
        if check_completeness:
            # 传入 last_update=None 强制触发完整性检查
            await updater.update_single_symbol(symbol, last_update=None, force_full=False)
            results["details"]["price"] = "Updated with completeness check (missing data auto-filled)"
        else:
            # 只做增量更新
            await updater.update_single_symbol(symbol, last_update=last_update, force_full=False)
            results["details"]["price"] = "Incremental update only"
        
        results["updated"].append("price")
        
        # 重新计算 Attention Features
        try:
            attention_result = AttentionService.update_attention_features(symbol, freq='D', save_to_db=True)
            if attention_result is not None:
                results["updated"].append("attention")
                results["details"]["attention"] = f"{len(attention_result)} rows computed"
            else:
                results["details"]["attention"] = "No data to compute"
        except Exception as e:
            logger.error(f"[Refresh] Attention calculation failed for {symbol}: {e}")
            results["details"]["attention_error"] = str(e)
        
        logger.info(f"[Refresh] ✅ {symbol} refresh completed: {results['updated']}")
        return results
        
    except Exception as e:
        logger.error(f"[Refresh] Failed to refresh {symbol}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/update-data", tags=["System"])
async def update_data(
    symbol: Optional[str] = Query(None, description="指定代币（留空则更新所有）"),
    update_price: bool = Query(True, description="更新价格数据"),
    update_attention: bool = Query(True, description="更新注意力数据"),
):
    """
    手动触发数据更新（兼容旧接口 + 新功能）
    """
    results = {
        "status": "success",
        "updated": [],
        "symbols_updated": []
    }
    
    try:
        updater = RealtimePriceUpdater()
        
        if symbol:
            # 更新单个代币
            symbol = symbol.upper()
            
            if update_price:
                session = get_session()
                try:
                    sym = session.query(Symbol).filter_by(symbol=symbol).first()
                    last_update = sym.last_price_update if sym else None
                finally:
                    session.close()
                
                await updater.update_single_symbol(symbol, last_update=last_update)
                results["updated"].append("price")
            
            if update_attention:
                try:
                    AttentionService.update_attention_features(symbol, freq='D', save_to_db=True)
                    results["updated"].append("attention")
                except Exception as e:
                    logger.warning(f"Attention update failed for {symbol}: {e}")
            
            results["symbols_updated"].append(symbol)
        else:
            # 更新所有代币
            if update_price:
                await updater.update_all_symbols()
                results["updated"].append("price")
                results["updated"].append("attention")  # update_all_symbols 会自动计算 attention
                
                # 获取更新了哪些代币
                symbols = updater.get_auto_update_symbols()
                results["symbols_updated"] = [s["symbol"] for s in symbols]
        
        logger.info(f"[Update] Completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"[Update] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
