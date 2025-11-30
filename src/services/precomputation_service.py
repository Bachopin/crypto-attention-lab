"""
Precomputation Service for Crypto Attention Lab

本模块负责预计算和存储静态/准静态数据，减少 API 请求时的实时计算开销。

预计算内容：
1. EventPerformance: 事件后的平均收益表现（每个 symbol 缓存到 Symbol 表）
   - lookahead_days=[1,3,5,10]（固定值）
   - 依赖日线价格数据（lookahead 以天为单位）

2. StateSnapshots: 状态特征快照（存储到 state_snapshots 表）
   - timeframe='1d' 和 '4h'
   - window_days=30（固定值）
   - 每个时间点一条记录

更新策略：
- 全量更新：首次或数据缺失时
- 增量更新：仅计算最新数据点
- 触发时机：attention_features 更新后自动触发
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database.models import Symbol, StateSnapshot, Price, AttentionFeature, get_session, get_engine
from src.features.event_performance import compute_event_performance, EventPerformance
from src.research.state_snapshot import compute_state_snapshot, StateSnapshot as SnapshotDataclass
from src.services.market_data_service import MarketDataService
from src.data.db_storage import load_price_data

logger = logging.getLogger(__name__)

# 预计算配置常量
DEFAULT_LOOKAHEAD_DAYS = [1, 3, 5, 10]  # 事件表现固定的前瞻天数
DEFAULT_SNAPSHOT_WINDOW = 30  # 状态快照固定的窗口天数
SNAPSHOT_TIMEFRAMES = ['1d', '4h']  # 支持的时间粒度
EVENT_PERFORMANCE_COOLDOWN_HOURS = 12  # 事件表现更新冷却期（小时）


class PrecomputationService:
    """预计算服务"""
    
    # ==================== Event Performance ====================
    
    @staticmethod
    def compute_and_store_event_performance(
        symbol: str,
        session: Optional[Session] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Dict[int, EventPerformance]]:
        """
        计算并存储事件表现统计
        
        策略：
        - force_refresh=True: 强制重新计算
        - force_refresh=False: 检查冷却期（12小时），未过冷却期则用缓存
        
        Args:
            symbol: 币种符号
            session: 数据库会话（可选）
            force_refresh: 是否强制刷新缓存
            
        Returns:
            事件表现统计字典
        """
        close_session = session is None
        if session is None:
            session = get_session()
            
        try:
            # 查找 Symbol 记录
            symbol_record = session.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if not symbol_record:
                logger.warning(f"Symbol {symbol} not found in database")
                return {}
            
            # 检查是否需要更新
            need_update = force_refresh
            
            if not need_update:
                if not symbol_record.event_performance_cache:
                    # 没有缓存，需要计算
                    need_update = True
                elif symbol_record.event_performance_updated_at:
                    # 检查冷却期
                    last_update = symbol_record.event_performance_updated_at
                    if last_update.tzinfo is None:
                        last_update = last_update.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - last_update).total_seconds() / 3600
                    if age_hours >= EVENT_PERFORMANCE_COOLDOWN_HOURS:
                        need_update = True
                        logger.info(f"Event performance cooldown passed for {symbol} ({age_hours:.1f}h >= {EVENT_PERFORMANCE_COOLDOWN_HOURS}h)")
                    else:
                        logger.debug(f"Event performance within cooldown for {symbol} ({age_hours:.1f}h < {EVENT_PERFORMANCE_COOLDOWN_HOURS}h)")
                else:
                    # 有缓存但没有更新时间，需要更新
                    need_update = True
            
            if not need_update:
                # 使用缓存
                cached = json.loads(symbol_record.event_performance_cache)
                return PrecomputationService._deserialize_event_performance(cached)
            
            # 计算事件表现
            logger.info(f"Computing event_performance for {symbol}...")
            result = compute_event_performance(
                symbol=symbol,
                lookahead_days=DEFAULT_LOOKAHEAD_DAYS,
            )
            
            if not result:
                logger.info(f"No event performance data for {symbol}")
                return {}
            
            # 序列化并存储
            serialized = PrecomputationService._serialize_event_performance(result)
            symbol_record.event_performance_cache = json.dumps(serialized, ensure_ascii=False)
            symbol_record.event_performance_updated_at = datetime.now(timezone.utc)
            
            session.commit()
            logger.info(f"Stored event_performance for {symbol}: {len(result)} event types")
            
            return result
            
        except Exception as e:
            logger.error(f"Error computing event_performance for {symbol}: {e}")
            session.rollback()
            return {}
        finally:
            if close_session:
                session.close()
    
    @staticmethod
    def get_cached_event_performance(
        symbol: str,
        session: Optional[Session] = None,
    ) -> Optional[Dict[str, Dict[int, EventPerformance]]]:
        """
        获取缓存的事件表现统计（不触发重新计算）
        
        Returns:
            缓存的事件表现统计，如果没有缓存则返回 None
        """
        close_session = session is None
        if session is None:
            session = get_session()
            
        try:
            symbol_record = session.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if symbol_record and symbol_record.event_performance_cache:
                cached = json.loads(symbol_record.event_performance_cache)
                return PrecomputationService._deserialize_event_performance(cached)
            return None
        finally:
            if close_session:
                session.close()
    
    @staticmethod
    def _serialize_event_performance(
        data: Dict[str, Dict[int, EventPerformance]]
    ) -> Dict[str, List[Dict]]:
        """序列化事件表现数据"""
        result = {}
        for event_type, horizons in data.items():
            result[event_type] = []
            for days, perf in horizons.items():
                result[event_type].append({
                    'lookahead_days': perf.lookahead_days,
                    'avg_return': perf.avg_return,
                    'sample_size': perf.sample_size,
                })
        return result
    
    @staticmethod
    def _deserialize_event_performance(
        data: Dict[str, List[Dict]]
    ) -> Dict[str, Dict[int, EventPerformance]]:
        """反序列化事件表现数据"""
        result = {}
        for event_type, perfs in data.items():
            result[event_type] = {}
            for p in perfs:
                days = p['lookahead_days']
                result[event_type][days] = EventPerformance(
                    event_type=event_type,
                    lookahead_days=days,
                    avg_return=p['avg_return'],
                    sample_size=p['sample_size'],
                )
        return result
    
    # ==================== State Snapshots ====================
    
    @staticmethod
    def compute_and_store_state_snapshots(
        symbol: str,
        timeframe: str = '1d',
        session: Optional[Session] = None,
        force_full: bool = False,
    ) -> int:
        """
        计算并存储状态快照
        
        策略：
        - 检查已有快照的最新时间
        - 如果没有数据或 force_full=True，执行全量计算
        - 否则执行增量计算（从最新快照之后开始）
        
        Args:
            symbol: 币种符号
            timeframe: 时间粒度 ('1d' 或 '4h')
            session: 数据库会话（可选）
            force_full: 是否强制全量更新
            
        Returns:
            新增的快照数量
        """
        close_session = session is None
        if session is None:
            session = get_session()
            
        try:
            # 查找 Symbol 记录
            symbol_upper = symbol.upper()
            symbol_record = session.query(Symbol).filter(Symbol.symbol == symbol_upper).first()
            if not symbol_record:
                logger.warning(f"Symbol {symbol} not found in database")
                return 0
            
            symbol_id = symbol_record.id
            
            # 获取价格数据范围
            price_range = PrecomputationService._get_price_data_range(symbol_upper, timeframe, session)
            if not price_range:
                logger.warning(f"No price data for {symbol} ({timeframe})")
                return 0
            
            price_start, price_end = price_range
            logger.info(f"Price data range for {symbol} ({timeframe}): {price_start} to {price_end}")
            
            # 检查已有快照的最新时间
            latest_snapshot = session.query(func.max(StateSnapshot.datetime)).filter(
                StateSnapshot.symbol_id == symbol_id,
                StateSnapshot.timeframe == timeframe,
                StateSnapshot.window_days == DEFAULT_SNAPSHOT_WINDOW,
            ).scalar()
            
            # 确定计算起始时间
            if force_full or latest_snapshot is None:
                # 全量更新：从价格数据开始 + window_days（需要足够历史）
                calc_start = price_start + timedelta(days=DEFAULT_SNAPSHOT_WINDOW)
                logger.info(f"Full snapshot computation for {symbol} ({timeframe}) from {calc_start}")
            else:
                # 增量更新：从最新快照之后开始
                # 确保 latest_snapshot 有时区信息
                if latest_snapshot.tzinfo is None:
                    latest_snapshot = latest_snapshot.replace(tzinfo=timezone.utc)
                if timeframe == '1d':
                    calc_start = latest_snapshot + timedelta(days=1)
                else:
                    calc_start = latest_snapshot + timedelta(hours=4)
                logger.info(f"Incremental snapshot for {symbol} ({timeframe}) from {calc_start}")
            
            # 如果起始时间已经超过数据范围，无需计算
            if calc_start > price_end:
                logger.info(f"No new snapshots needed for {symbol} ({timeframe})")
                return 0
            
            # 生成需要计算的时间点列表
            time_points = PrecomputationService._generate_time_points(calc_start, price_end, timeframe)
            if not time_points:
                logger.info(f"No time points to compute for {symbol} ({timeframe})")
                return 0
            
            logger.info(f"Computing {len(time_points)} snapshots for {symbol} ({timeframe})...")
            
            # 预加载数据以提高效率
            # 计算需要的回溯时间（window_days * 2 + 一些余量）
            data_start = calc_start - timedelta(days=DEFAULT_SNAPSHOT_WINDOW * 2 + 7)
            unified_df = MarketDataService.get_aligned_data(
                symbol_upper, 
                start=data_start, 
                end=price_end, 
                timeframe=timeframe
            )
            
            if unified_df.empty:
                logger.warning(f"No aligned data for {symbol} ({timeframe})")
                return 0
            
            # 批量计算和存储
            new_count = 0
            batch_size = 100
            snapshots_to_add = []
            
            for as_of in time_points:
                try:
                    snapshot = compute_state_snapshot(
                        symbol=symbol_upper,
                        as_of=as_of,
                        timeframe=timeframe,
                        window_days=DEFAULT_SNAPSHOT_WINDOW,
                        price_df=unified_df,
                        attention_df=unified_df,
                    )
                    
                    if snapshot and (snapshot.features or snapshot.raw_stats):
                        db_snapshot = StateSnapshot.from_computed(
                            symbol_id=symbol_id,
                            dt=as_of,
                            timeframe=timeframe,
                            features=snapshot.features,
                            raw_stats=snapshot.raw_stats,
                            window_days=DEFAULT_SNAPSHOT_WINDOW,
                        )
                        snapshots_to_add.append(db_snapshot)
                        new_count += 1
                        
                        # 批量提交
                        if len(snapshots_to_add) >= batch_size:
                            session.bulk_save_objects(snapshots_to_add)
                            session.commit()
                            snapshots_to_add = []
                            logger.debug(f"Committed {batch_size} snapshots for {symbol}")
                            
                except Exception as e:
                    logger.warning(f"Error computing snapshot for {symbol} at {as_of}: {e}")
                    continue
            
            # 提交剩余的
            if snapshots_to_add:
                session.bulk_save_objects(snapshots_to_add)
                session.commit()
            
            logger.info(f"Stored {new_count} new snapshots for {symbol} ({timeframe})")
            return new_count
            
        except Exception as e:
            logger.error(f"Error computing state_snapshots for {symbol}: {e}")
            session.rollback()
            return 0
        finally:
            if close_session:
                session.close()
    
    @staticmethod
    def get_cached_state_snapshot(
        symbol: str,
        as_of: datetime,
        timeframe: str = '1d',
        session: Optional[Session] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        获取缓存的状态快照
        
        Args:
            symbol: 币种符号
            as_of: 快照时间
            timeframe: 时间粒度
            session: 数据库会话（可选）
            
        Returns:
            快照字典，如果没有缓存则返回 None
        """
        close_session = session is None
        if session is None:
            session = get_session()
            
        try:
            symbol_record = session.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if not symbol_record:
                return None
            
            # 查找最接近的快照（向前）
            snapshot = session.query(StateSnapshot).filter(
                StateSnapshot.symbol_id == symbol_record.id,
                StateSnapshot.timeframe == timeframe,
                StateSnapshot.window_days == DEFAULT_SNAPSHOT_WINDOW,
                StateSnapshot.datetime <= as_of,
            ).order_by(StateSnapshot.datetime.desc()).first()
            
            if snapshot:
                return snapshot.to_dict()
            return None
            
        finally:
            if close_session:
                session.close()
    
    @staticmethod
    def get_state_snapshots_range(
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = '1d',
        session: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取时间范围内的所有状态快照
        
        Returns:
            快照列表
        """
        close_session = session is None
        if session is None:
            session = get_session()
            
        try:
            symbol_record = session.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
            if not symbol_record:
                return []
            
            snapshots = session.query(StateSnapshot).filter(
                StateSnapshot.symbol_id == symbol_record.id,
                StateSnapshot.timeframe == timeframe,
                StateSnapshot.window_days == DEFAULT_SNAPSHOT_WINDOW,
                StateSnapshot.datetime >= start,
                StateSnapshot.datetime <= end,
            ).order_by(StateSnapshot.datetime).all()
            
            return [s.to_dict() for s in snapshots]
            
        finally:
            if close_session:
                session.close()
    
    @staticmethod
    def _get_price_data_range(
        symbol: str, 
        timeframe: str,
        session: Session,
    ) -> Optional[Tuple[datetime, datetime]]:
        """获取价格数据的时间范围"""
        # 先获取 symbol_id
        symbol_record = session.query(Symbol).filter(Symbol.symbol == symbol.upper()).first()
        if not symbol_record:
            return None
        
        # 将 timeframe 转换为数据库格式
        tf_map = {'1d': '1d', '4h': '4h', 'd': '1d', '4H': '4h'}
        db_timeframe = tf_map.get(timeframe.lower(), timeframe)
        
        result = session.query(
            func.min(Price.datetime),
            func.max(Price.datetime)
        ).filter(
            Price.symbol_id == symbol_record.id,
            Price.timeframe == db_timeframe,
        ).first()
        
        if result and result[0] and result[1]:
            start_dt = result[0]
            end_dt = result[1]
            
            # 确保有时区信息
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
                
            return (start_dt, end_dt)
        return None
    
    @staticmethod
    def _generate_time_points(
        start: datetime, 
        end: datetime, 
        timeframe: str,
    ) -> List[datetime]:
        """生成时间点列表"""
        points = []
        current = start
        
        if timeframe == '1d':
            delta = timedelta(days=1)
        elif timeframe == '4h':
            delta = timedelta(hours=4)
        else:
            delta = timedelta(days=1)
        
        while current <= end:
            points.append(current)
            current += delta
        
        return points
    
    # ==================== 综合更新 ====================
    
    @staticmethod
    def update_all_precomputations(
        symbol: str,
        session: Optional[Session] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        更新某个 symbol 的所有预计算数据
        
        更新策略：
        - force_refresh=True: 强制刷新所有预计算
        - force_refresh=False: 
          - event_performance: 检查冷却期（12h），过期则更新
          - state_snapshots: 增量更新（只计算新时间点）
        
        Args:
            symbol: 币种符号
            session: 数据库会话（可选）
            force_refresh: 是否强制刷新
            
        Returns:
            更新结果摘要
        """
        close_session = session is None
        if session is None:
            session = get_session()
            
        results = {
            'symbol': symbol,
            'event_performance': None,
            'state_snapshots': {},
        }
        
        try:
            # 1. 更新事件表现
            event_perf = PrecomputationService.compute_and_store_event_performance(
                symbol=symbol,
                session=session,
                force_refresh=force_refresh,
            )
            results['event_performance'] = len(event_perf) if event_perf else 0
            
            # 2. 更新状态快照（所有时间粒度）
            for tf in SNAPSHOT_TIMEFRAMES:
                count = PrecomputationService.compute_and_store_state_snapshots(
                    symbol=symbol,
                    timeframe=tf,
                    session=session,
                    force_full=force_refresh,
                )
                results['state_snapshots'][tf] = count
            
            logger.info(f"Precomputation complete for {symbol}: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error in update_all_precomputations for {symbol}: {e}")
            return results
        finally:
            if close_session:
                session.close()
    
    @staticmethod
    def update_precomputations_for_all_symbols(
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        更新所有活跃 symbol 的预计算数据
        
        Returns:
            所有 symbol 的更新结果列表
        """
        session = get_session()
        results = []
        
        try:
            # 获取所有活跃的 symbol
            symbols = session.query(Symbol).filter(Symbol.is_active == True).all()
            
            for sym in symbols:
                result = PrecomputationService.update_all_precomputations(
                    symbol=sym.symbol,
                    session=session,
                    force_refresh=force_refresh,
                )
                results.append(result)
            
            return results
            
        finally:
            session.close()


# 便捷函数
def trigger_precomputation_after_feature_update(symbol: str):
    """
    特征更新后触发预计算
    
    设计为轻量级调用，可以在 AttentionService 更新后调用
    """
    try:
        PrecomputationService.update_all_precomputations(symbol, force_refresh=True)
    except Exception as e:
        logger.error(f"Failed to trigger precomputation for {symbol}: {e}")


if __name__ == "__main__":
    # 测试代码
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 测试单个 symbol
    result = PrecomputationService.update_all_precomputations("ZEC", force_refresh=True)
    print(f"Result: {result}")
