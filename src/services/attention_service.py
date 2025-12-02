"""
Service layer for attention features.
Orchestrates data loading, calculation, and persistence.
Supports both full and incremental calculation modes.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import pandas as pd

from src.data.db_storage import load_price_data, load_news_data, get_db, USE_DATABASE, load_attention_data
from src.data.google_trends_fetcher import get_google_trends_series
from src.data.twitter_attention_fetcher import get_twitter_volume_series
from src.features.calculators import calculate_composite_attention
from src.features.event_detectors import (
    detect_attention_spikes, 
    detect_events_per_row,
    events_from_json,
    AttentionEvent
)
from src.config.settings import ROLLING_WINDOW_CONTEXT_DAYS
from typing import List

logger = logging.getLogger(__name__)

# 预计算事件使用的默认参数
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MIN_QUANTILE = 0.8

class AttentionService:
    @staticmethod
    def get_attention_events(
        symbol: str,
        start: Optional[pd.Timestamp] = None,
        end: Optional[pd.Timestamp] = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        min_quantile: float = DEFAULT_MIN_QUANTILE,
        auto_update: bool = True,
    ) -> List[AttentionEvent]:
        """
        Get attention events for a symbol.
        
        策略：
        - 如果参数等于默认值 (lookback_days=30, min_quantile=0.8)，优先读取预计算缓存
        - 如果参数不等于默认值，实时计算
        - 如果没有预计算数据但有价格数据，且 auto_update=True，触发全量/增量计算
        - 如果没有预计算数据，回退到实时计算
        
        Args:
            symbol: Symbol name.
            start: Start datetime.
            end: End datetime.
            lookback_days: Lookback window for quantile (default: 30).
            min_quantile: Quantile threshold (default: 0.8).
            auto_update: 如果缺少预计算事件，是否自动触发更新（默认 True）。
            
        Returns:
            List of AttentionEvent objects.
        """
        # 1. 判断是否可以使用预计算缓存（仅当参数等于默认值时）
        use_cache = (lookback_days == DEFAULT_LOOKBACK_DAYS and min_quantile == DEFAULT_MIN_QUANTILE)
        
        # 2. 如果使用缓存，加载完整的数据集（忽略 start/end 参数）
        # 这样可以确保读取到所有预计算的事件，然后在返回前根据 start/end 筛选
        if use_cache:
            df_full = load_attention_data(symbol, start=None, end=None)
            if not df_full.empty and 'detected_events' in df_full.columns:
                # Ensure datetime is present and valid
                if 'datetime' in df_full.columns:
                    df_full = df_full.dropna(subset=['datetime'])
                
                # 尝试从预计算字段读取
                precomputed_events: List[AttentionEvent] = []
                has_precomputed = False
                
                for _, row in df_full.iterrows():
                    events_json = row.get('detected_events')
                    if events_json:
                        has_precomputed = True
                        dt = pd.to_datetime(row['datetime'])
                        precomputed_events.extend(events_from_json(dt, events_json))
                
                if has_precomputed:
                    # 根据 start/end 筛选事件
                    if start or end:
                        filtered_events = []
                        for event in precomputed_events:
                            event_time = pd.to_datetime(event.datetime)
                            if start and event_time < start:
                                continue
                            if end and event_time > end:
                                continue
                            filtered_events.append(event)
                        logger.debug(f"Using precomputed events for {symbol}: {len(filtered_events)}/{len(precomputed_events)} events (filtered by time range)")
                        return filtered_events
                    else:
                        logger.debug(f"Using precomputed events for {symbol}: {len(precomputed_events)} events")
                        return precomputed_events
        
        # 3. 实时计算或缓存不可用时，加载指定时间范围的数据
        df = load_attention_data(symbol, start, end)
        if df.empty:
            return []
        
        # Ensure datetime is present and valid
        if 'datetime' in df.columns:
            df = df.dropna(subset=['datetime'])
        
        # 4. 如果使用缓存但没有预计算数据，检查数据完整性并尝试自动更新
        if use_cache and auto_update and not df.empty:
            # 检查特征数据是否与价格数据长度匹配
            try:
                # 获取价格数据长度
                price_data = load_price_data(symbol, timeframe='1d')
                if isinstance(price_data, tuple):
                    price_df, _ = price_data
                else:
                    price_df = price_data
                
                if price_df is not None and not price_df.empty:
                    price_count = len(price_df)
                    feature_count = len(df)
                    coverage = feature_count / price_count if price_count > 0 else 0
                    
                    # 如果覆盖率 < 90%，触发全量更新
                    if coverage < 0.9:
                        logger.info(f"[AutoUpdate] {symbol} feature coverage {coverage*100:.1f}% < 90% ({feature_count}/{price_count}), triggering full update...")
                        try:
                            # 覆盖率不足，使用全量更新确保数据完整
                            AttentionService.update_attention_features(symbol, freq='D', save_to_db=True)
                            # 更新后重新读取（禁用 auto_update 避免无限循环）
                            updated_events = AttentionService.get_attention_events(
                                symbol, start, end, lookback_days, min_quantile, auto_update=False
                            )
                            if updated_events:
                                return updated_events
                            else:
                                logger.warning(f"[AutoUpdate] Update finished but no events found for {symbol}. Falling back to real-time.")
                        except Exception as e:
                            logger.warning(f"[AutoUpdate] Failed to update features for {symbol}: {e}")
                    elif 'detected_events' not in df.columns or df['detected_events'].notna().sum() == 0:
                        # 覆盖率足够，但没有预计算事件字段或全部为空
                        logger.info(f"[AutoUpdate] {symbol} has no precomputed events (coverage={coverage*100:.1f}%), triggering update...")
                        try:
                            AttentionService.update_attention_features_incremental(symbol, freq='D', save_to_db=True)
                            updated_events = AttentionService.get_attention_events(
                                symbol, start, end, lookback_days, min_quantile, auto_update=False
                            )
                            if updated_events:
                                return updated_events
                        except Exception as e:
                            logger.warning(f"[AutoUpdate] Failed to update features for {symbol}: {e}")
            except Exception as check_err:
                logger.warning(f"[AutoUpdate] Failed to check data coverage for {symbol}: {check_err}")
        
        # 5. 实时计算（参数非默认值 或 没有预计算数据 或 预计算为空）
        if not use_cache:
            logger.debug(f"Real-time calculation for {symbol} (non-default params: lookback={lookback_days}, quantile={min_quantile})")
        else:
            logger.debug(f"No precomputed events for {symbol} (or update failed), calculating in real-time")
        
        return detect_attention_spikes(df, lookback_days, min_quantile)

    @staticmethod
    def update_attention_features(
        symbol: str,
        freq: str = 'D',
        save_to_db: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        Orchestrate the calculation of attention features for a symbol.
        
        1. Loads price, news, google trends, and twitter data.
        2. Calls the pure calculation logic.
        3. Saves the result to the database.
        
        Args:
            symbol: Symbol name (e.g., 'ZEC')
            freq: Frequency ('D' or '4H')
            save_to_db: Whether to persist results
            
        Returns:
            DataFrame with features or None if failed.
        """
        symbol = symbol.upper()
        freq = freq.upper()
        
        logger.info(f"Processing attention features for {symbol} (freq={freq})")
        
        # 1. Load Price Data (Base for time index)
        # We always use 1d price data to determine the date range, even for 4H attention
        price_data = load_price_data(symbol, timeframe='1d')
        if isinstance(price_data, tuple):
            price_df, _ = price_data
        else:
            price_df = price_data
            
        if price_df is None or price_df.empty:
            logger.error(f"No price data available for {symbol}, cannot generate attention features")
            return None
            
        # Determine date range
        if 'timestamp' in price_df.columns:
            price_df['datetime'] = pd.to_datetime(price_df['timestamp'], unit='ms', utc=True)
        elif 'date' not in price_df.columns and 'datetime' not in price_df.columns:
            logger.error(f"Price data for {symbol} has no datetime column")
            return None
            
        date_col = 'datetime' if 'datetime' in price_df.columns else 'date'
        date_range = pd.to_datetime(price_df[date_col], utc=True)
        start_date = date_range.min()
        end_date = date_range.max()
        
        # 2. Load Auxiliary Data
        # News - extend end_date to include all news for the current day's candle
        # Price datetime is the candle open time (e.g., 2025-12-01 00:00 UTC),
        # but news can arrive throughout the day until the next candle opens.
        # We extend to end_date + 1 day to capture all relevant news.
        news_end_date = end_date + pd.Timedelta(days=1)
        news_df = load_news_data(symbol, start=start_date, end=news_end_date)
        
        # Google Trends (fetch extra 7 days for rolling window context)
        gt_start = start_date - pd.Timedelta(days=7)
        try:
            google_trends_df = get_google_trends_series(symbol, gt_start, end_date)
        except Exception as e:
            logger.warning(f"Failed to load Google Trends for {symbol}: {e}")
            google_trends_df = None
            
        # Twitter Volume
        try:
            twitter_volume_df = get_twitter_volume_series(symbol, gt_start, end_date)
        except Exception as e:
            logger.warning(f"Failed to load Twitter volume for {symbol}: {e}")
            twitter_volume_df = None
            
        # 3. Calculate Features (Pure Logic)
        result_df = calculate_composite_attention(
            symbol=symbol,
            price_df=price_df,
            news_df=news_df,
            google_trends_df=google_trends_df,
            twitter_volume_df=twitter_volume_df,
            freq=freq
        )
        
        if result_df is None or result_df.empty:
            logger.warning(f"Calculation returned empty result for {symbol}")
            return None
        
        # 3.5 计算并添加事件检测结果
        result_df = detect_events_per_row(result_df, lookback_days=30, min_quantile=0.8)
        logger.info(f"Detected events for {len(result_df)} rows for {symbol}")
        
        # 3.6 计算预计算字段 (价格派生指标)
        try:
            from src.features.precomputed_fields import compute_all_precomputed_fields
            precomputed_df = compute_all_precomputed_fields(price_df, result_df)
            
            if not precomputed_df.empty:
                # 合并预计算字段到结果
                result_df['datetime'] = pd.to_datetime(result_df['datetime'], utc=True)
                result_df = result_df.set_index('datetime')
                
                # 只添加结果中不存在的列
                for col in precomputed_df.columns:
                    if col not in result_df.columns:
                        result_df[col] = precomputed_df[col]
                
                result_df = result_df.reset_index()
                logger.info(f"Added precomputed fields for {symbol}")
        except Exception as precomp_err:
            logger.warning(f"Failed to compute precomputed fields for {symbol}: {precomp_err}")
            # Ensure datetime column exists (may be stuck as index if exception occurred mid-process)
            if 'datetime' not in result_df.columns and result_df.index.name == 'datetime':
                result_df = result_df.reset_index()
            
        # 4. Persist Results
        if USE_DATABASE and save_to_db:
            try:
                db = get_db()
                # Pass timeframe param to distinguish frequencies
                db.save_attention_features(symbol, result_df.to_dict('records'), timeframe=freq)
                logger.info(f"Saved {len(result_df)} attention rows for {symbol} (freq={freq})")
                
                # 触发预计算更新（异步风格，失败不影响主流程）
                try:
                    from src.services.precomputation_service import PrecomputationService
                    PrecomputationService.update_all_precomputations(symbol, force_refresh=True)
                    logger.info(f"Triggered precomputation update for {symbol}")
                except Exception as precomp_err:
                    logger.warning(f"Precomputation update failed for {symbol}: {precomp_err}")
                    
            except TypeError as te:
                logger.warning(
                    f"save_attention_features does not support timeframe param yet; "
                    f"Data returned but not saved correctly for 4H. Error: {te}"
                )
            except Exception as exc:
                logger.error(f"Failed to persist attention features: {exc}")
                
        return result_df

    @staticmethod
    def update_attention_features_incremental(
        symbol: str,
        freq: str = 'D',
        save_to_db: bool = True,
        force_google_trends: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        增量计算注意力特征
        
        策略：
        1. 检查数据库中最新的特征时间戳
        2. 仅加载该时间戳之后的新数据
        3. 保留滚动窗口所需的历史上下文（用于 z-score 等计算）
        4. 仅追加保存新计算的特征（避免全量 upsert）
        
        Args:
            symbol: Symbol name (e.g., 'ZEC')
            freq: Frequency ('D' or '4H')
            save_to_db: Whether to persist results
            force_google_trends: 是否强制更新 Google Trends（受冷却期控制）
            
        Returns:
            DataFrame with newly calculated features, or None if no new data.
        """
        symbol = symbol.upper()
        freq = freq.upper()
        
        logger.info(f"[Incremental] Processing attention features for {symbol} (freq={freq})")
        
        # 1. 获取数据库中最新的特征时间戳
        db = get_db() if USE_DATABASE else None
        latest_feature_dt = None
        
        if db:
            try:
                latest_feature_dt = db.get_latest_attention_datetime(symbol, freq)
            except Exception as e:
                logger.warning(f"Failed to get latest attention datetime: {e}")
        
        # 2. 加载价格数据确定完整时间范围
        price_data = load_price_data(symbol, timeframe='1d')
        if isinstance(price_data, tuple):
            price_df, _ = price_data
        else:
            price_df = price_data
            
        if price_df is None or price_df.empty:
            logger.error(f"No price data available for {symbol}")
            return None
            
        # 处理时间列
        if 'timestamp' in price_df.columns:
            price_df['datetime'] = pd.to_datetime(price_df['timestamp'], unit='ms', utc=True)
        elif 'date' not in price_df.columns and 'datetime' not in price_df.columns:
            logger.error(f"Price data for {symbol} has no datetime column")
            return None
            
        date_col = 'datetime' if 'datetime' in price_df.columns else 'date'
        price_df[date_col] = pd.to_datetime(price_df[date_col], utc=True)
        
        price_max_dt = price_df[date_col].max()
        price_min_dt = price_df[date_col].min()
        
        # 3. 确定增量计算范围
        if latest_feature_dt is None:
            # 首次计算，使用全量模式
            logger.info(f"[Incremental] No existing features for {symbol}, running full calculation")
            return AttentionService.update_attention_features(symbol, freq, save_to_db)
        
        latest_feature_dt = pd.to_datetime(latest_feature_dt, utc=True)
        
        # 检查是否有新数据
        if latest_feature_dt >= price_max_dt:
            logger.info(f"[Incremental] {symbol} is up-to-date (latest: {latest_feature_dt.date()})")
            # 返回最近的特征数据用于 WebSocket 广播
            if db:
                return db.get_attention_features(symbol, start=latest_feature_dt, timeframe=freq)
            return None
        
        # 计算需要的数据范围
        # 起始时间 = 最新特征时间 - 滚动窗口天数（用于 z-score 上下文）
        context_start = latest_feature_dt - timedelta(days=ROLLING_WINDOW_CONTEXT_DAYS)
        context_start = max(context_start, price_min_dt)
        
        # 新数据起始时间 = 最新特征时间的下一天
        new_data_start = latest_feature_dt + timedelta(days=1)
        
        logger.info(
            f"[Incremental] {symbol}: calculating from {new_data_start.date()} to {price_max_dt.date()} "
            f"(context from {context_start.date()})"
        )
        
        # 4. 加载所需范围的价格数据
        price_df_subset = price_df[price_df[date_col] >= context_start].copy()
        
        if price_df_subset.empty:
            logger.warning(f"No price data in calculation range for {symbol}")
            return None
        
        # 5. 加载新闻数据（仅新数据范围，因为新闻不需要滚动上下文）
        # Extend end date by 1 day to capture all news for the current candle
        news_end_date = price_max_dt + timedelta(days=1)
        news_df = load_news_data(symbol, start=new_data_start, end=news_end_date)
        
        # 6. 加载 Google Trends（根据 force_google_trends 决定）
        google_trends_df = None
        if force_google_trends:
            try:
                # 需要包含上下文范围
                gt_start = context_start - pd.Timedelta(days=7)
                google_trends_df = get_google_trends_series(symbol, gt_start, price_max_dt)
                logger.info(f"[Incremental] Google Trends updated for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to load Google Trends for {symbol}: {e}")
        else:
            # 使用缓存的 Google Trends 数据
            try:
                gt_start = context_start - pd.Timedelta(days=7)
                # force_refresh=False 会使用缓存
                google_trends_df = get_google_trends_series(symbol, gt_start, price_max_dt, force_refresh=False)
            except Exception as e:
                logger.warning(f"Failed to load cached Google Trends for {symbol}: {e}")
        
        # 7. Twitter Volume（当前为占位实现，返回 0）
        twitter_volume_df = None
        try:
            twitter_volume_df = get_twitter_volume_series(symbol, context_start, price_max_dt)
        except Exception as e:
            logger.debug(f"Twitter volume not available for {symbol}: {e}")
        
        # 8. 计算特征（使用完整上下文范围）
        result_df = calculate_composite_attention(
            symbol=symbol,
            price_df=price_df_subset,
            news_df=news_df,
            google_trends_df=google_trends_df,
            twitter_volume_df=twitter_volume_df,
            freq=freq
        )
        
        if result_df is None or result_df.empty:
            logger.warning(f"Calculation returned empty result for {symbol}")
            return None
        
        # 8.5 计算并添加事件检测结果（在完整上下文上计算，确保分位数准确）
        result_df = detect_events_per_row(result_df, lookback_days=30, min_quantile=0.8)
        
        # 8.6 计算预计算字段（使用完整上下文范围以确保滚动计算准确）
        try:
            from src.features.precomputed_fields import compute_all_precomputed_fields
            precomputed_df = compute_all_precomputed_fields(price_df_subset, result_df)
            
            if not precomputed_df.empty:
                result_df['datetime'] = pd.to_datetime(result_df['datetime'], utc=True)
                result_df = result_df.set_index('datetime')
                
                for col in precomputed_df.columns:
                    if col not in result_df.columns:
                        result_df[col] = precomputed_df[col]
                
                result_df = result_df.reset_index()
                logger.debug(f"[Incremental] Added precomputed fields for {symbol}")
        except Exception as precomp_err:
            logger.warning(f"[Incremental] Failed to compute precomputed fields for {symbol}: {precomp_err}")
        
        # 9. 仅保留新数据部分（去掉上下文窗口部分）
        result_df['datetime'] = pd.to_datetime(result_df['datetime'], utc=True)
        new_features_df = result_df[result_df['datetime'] >= new_data_start].copy()
        
        if new_features_df.empty:
            logger.info(f"[Incremental] No new features calculated for {symbol}")
            return result_df.tail(1)  # 返回最新一条用于广播
        
        # 10. 保存新特征
        if USE_DATABASE and save_to_db and db:
            try:
                db.save_attention_features(symbol, new_features_df.to_dict('records'), timeframe=freq)
                logger.info(f"[Incremental] Saved {len(new_features_df)} new attention rows for {symbol}")
                
                # 触发预计算更新
                # - state_snapshots: 增量更新（只计算新时间点）
                # - event_performance: 检查冷却期（12h），过期则重算
                try:
                    from src.services.precomputation_service import PrecomputationService
                    PrecomputationService.update_all_precomputations(symbol, force_refresh=False)
                    logger.debug(f"[Incremental] Triggered precomputation update for {symbol}")
                except Exception as precomp_err:
                    logger.warning(f"[Incremental] Precomputation update failed for {symbol}: {precomp_err}")
                    
            except Exception as exc:
                logger.error(f"Failed to persist incremental attention features: {exc}")
        
        return new_features_df

