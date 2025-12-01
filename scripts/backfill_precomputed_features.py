#!/usr/bin/env python3
"""
Backfill Precomputed Features

本脚本用于填充 AttentionFeature 表中的预计算特征字段。

功能：
1. 从 Price 表读取价格数据，计算收益率、波动率等
2. 计算 State Features (规范化特征)
3. 计算 Forward Returns (前瞻收益，仅历史数据)
4. 生成 Feature Vector (用于 pgvector)

使用方法:
    python scripts/backfill_precomputed_features.py [--symbol ZEC] [--force]

参数:
    --symbol: 指定币种，默认处理所有
    --force: 强制重新计算所有记录
    --days: 只处理最近 N 天的数据
"""

import os
import sys
from pathlib import Path
import argparse

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def compute_rolling_returns(prices: pd.Series, windows: List[int] = [1, 7, 30, 60]) -> Dict[str, pd.Series]:
    """计算滚动收益率"""
    results = {}
    log_ret = np.log(prices / prices.shift(1))
    
    for w in windows:
        if w == 1:
            results[f'return_{w}d'] = log_ret  # 日收益
        else:
            results[f'return_{w}d'] = log_ret.rolling(window=w).sum()  # 累计对数收益
    
    return results


def compute_rolling_volatility(prices: pd.Series, windows: List[int] = [7, 30, 60]) -> Dict[str, pd.Series]:
    """计算滚动波动率"""
    results = {}
    log_ret = np.log(prices / prices.shift(1))
    
    for w in windows:
        results[f'volatility_{w}d'] = log_ret.rolling(window=w).std() * np.sqrt(252)  # 年化
    
    return results


def compute_volume_zscore(volume: pd.Series, windows: List[int] = [7, 30]) -> Dict[str, pd.Series]:
    """计算成交量 z-score"""
    results = {}
    
    for w in windows:
        rolling_mean = volume.rolling(window=w).mean()
        rolling_std = volume.rolling(window=w).std()
        # 当前值相对于滚动窗口的 z-score
        results[f'volume_zscore_{w}d'] = (volume - rolling_mean) / rolling_std
    
    return results


def compute_high_low(high: pd.Series, low: pd.Series, windows: List[int] = [30, 60]) -> Dict[str, pd.Series]:
    """计算滚动高低点"""
    results = {}
    
    for w in windows:
        results[f'high_{w}d'] = high.rolling(window=w).max()
        results[f'low_{w}d'] = low.rolling(window=w).min()
    
    return results


def compute_state_features(df: pd.DataFrame, windows: List[int] = [7, 30, 60]) -> Dict[str, pd.Series]:
    """计算 State Features (规范化特征)"""
    results = {}
    
    # 收益率 z-score
    log_ret = np.log(df['close'] / df['close'].shift(1))
    for w in windows:
        win_ret = log_ret.rolling(window=w).sum()
        hist_mean = win_ret.rolling(window=w*2).mean()
        hist_std = win_ret.rolling(window=w*2).std()
        results[f'feat_ret_zscore_{w}d'] = (win_ret - hist_mean) / hist_std
    
    # 波动率 z-score
    for w in windows:
        vol = log_ret.rolling(window=w).std()
        hist_mean = vol.rolling(window=w*2).mean()
        hist_std = vol.rolling(window=w*2).std()
        results[f'feat_vol_zscore_{w}d'] = (vol - hist_mean) / hist_std
    
    # 注意力趋势 (7 天斜率)
    if 'composite_attention_score' in df.columns:
        att = df['composite_attention_score'].fillna(0)
        # 简单线性斜率
        def slope_7d(x):
            if len(x) < 7 or x.isna().all():
                return np.nan
            y = x.values
            x_vals = np.arange(len(y))
            mask = ~np.isnan(y)
            if mask.sum() < 3:
                return np.nan
            slope = np.polyfit(x_vals[mask], y[mask], 1)[0]
            return slope
        
        results['feat_att_trend_7d'] = att.rolling(window=7).apply(slope_7d, raw=False)
    
    # 通道占比
    if all(col in df.columns for col in ['news_channel_score', 'google_trend_zscore', 'twitter_volume_zscore']):
        news_z = df['news_channel_score'].abs().fillna(0)
        google_z = df['google_trend_zscore'].abs().fillna(0)
        twitter_z = df['twitter_volume_zscore'].abs().fillna(0)
        
        total_z = news_z + google_z + twitter_z
        total_z = total_z.replace(0, 1.0)
        
        results['feat_att_news_share'] = news_z / total_z
        results['feat_att_google_share'] = google_z / total_z
        results['feat_att_twitter_share'] = twitter_z / total_z
    
    # 情绪特征
    if 'bullish_attention' in df.columns and 'bearish_attention' in df.columns:
        diff = df['bullish_attention'].fillna(0) - df['bearish_attention'].fillna(0)
        diff_std = diff.rolling(window=60).std()
        results['feat_bullish_minus_bearish'] = diff / diff_std.replace(0, 1)
    
    return results


def compute_forward_returns(prices: pd.Series, lookaheads: List[int] = [3, 7, 30]) -> Dict[str, pd.Series]:
    """计算前瞻收益（用于历史分析）"""
    results = {}
    
    for n in lookaheads:
        # 向前看 n 天的收益
        future_price = prices.shift(-n)
        results[f'forward_return_{n}d'] = (future_price / prices) - 1
    
    return results


def compute_max_drawdown(prices: pd.Series, windows: List[int] = [7, 30]) -> Dict[str, pd.Series]:
    """计算前瞻最大回撤"""
    results = {}
    
    for w in windows:
        # 计算未来 w 天窗口内的最大回撤
        mdd_list = []
        for i in range(len(prices)):
            if i + w >= len(prices):
                mdd_list.append(np.nan)
                continue
            
            future_slice = prices.iloc[i:i+w+1]
            if len(future_slice) < 2:
                mdd_list.append(np.nan)
                continue
            
            # 从当前价格开始计算最大回撤
            start_price = future_slice.iloc[0]
            running_max = start_price
            max_dd = 0.0
            
            for p in future_slice.iloc[1:]:
                running_max = max(running_max, p)
                dd = (running_max - p) / running_max if running_max > 0 else 0
                max_dd = max(max_dd, dd)
            
            mdd_list.append(max_dd)
        
        results[f'max_drawdown_{w}d'] = pd.Series(mdd_list, index=prices.index)
    
    return results


def build_feature_vector(row: pd.Series) -> Optional[List[float]]:
    """构建 12 维特征向量"""
    feature_cols = [
        'feat_ret_zscore_30d',
        'feat_vol_zscore_30d',
        'composite_attention_zscore',
        'feat_att_trend_7d',
        'feat_att_news_share',
        'feat_att_google_share',
        'feat_att_twitter_share',
        'feat_bullish_minus_bearish',
        'feat_sentiment_mean',
        'volume_zscore_30d',
        'google_trend_zscore',
        'twitter_volume_zscore',
    ]
    
    vector = []
    for col in feature_cols:
        val = row.get(col, 0.0)
        if pd.isna(val) or np.isinf(val):
            val = 0.0
        vector.append(float(val))
    
    return vector


def backfill_symbol(
    session,
    symbol: str,
    symbol_id: int,
    price_df: pd.DataFrame,
    attention_df: pd.DataFrame,
    force: bool = False
) -> int:
    """回填单个币种的预计算字段"""
    
    if price_df.empty:
        logger.warning(f"  {symbol}: 无价格数据，跳过")
        return 0
    
    # 准备数据
    price_df = price_df.sort_values('datetime').copy()
    price_df.set_index('datetime', inplace=True)
    
    # 计算各类特征
    logger.info(f"  计算滚动收益率...")
    returns = compute_rolling_returns(price_df['close'])
    
    logger.info(f"  计算滚动波动率...")
    volatility = compute_rolling_volatility(price_df['close'])
    
    logger.info(f"  计算成交量 z-score...")
    vol_zscore = compute_volume_zscore(price_df['volume'])
    
    logger.info(f"  计算高低点...")
    high_low = compute_high_low(price_df['high'], price_df['low'])
    
    # 合并注意力数据
    if not attention_df.empty:
        att_df = attention_df.sort_values('datetime').copy()
        att_df.set_index('datetime', inplace=True)
        # 合并价格和注意力
        merged = price_df.join(att_df, how='left', rsuffix='_att')
    else:
        merged = price_df
    
    logger.info(f"  计算 State Features...")
    state_features = compute_state_features(merged)
    
    logger.info(f"  计算前瞻收益...")
    forward_returns = compute_forward_returns(price_df['close'])
    
    logger.info(f"  计算最大回撤...")
    max_drawdowns = compute_max_drawdown(price_df['close'])
    
    # 合并所有特征
    all_features = pd.DataFrame(index=price_df.index)
    
    # 价格快照
    all_features['close_price'] = price_df['close']
    all_features['open_price'] = price_df['open']
    all_features['high_price'] = price_df['high']
    all_features['low_price'] = price_df['low']
    all_features['volume'] = price_df['volume']
    
    # 合并计算结果
    for name, series in returns.items():
        all_features[name] = series
    for name, series in volatility.items():
        all_features[name] = series
    for name, series in vol_zscore.items():
        all_features[name] = series
    for name, series in high_low.items():
        all_features[name] = series
    for name, series in state_features.items():
        all_features[name] = series
    for name, series in forward_returns.items():
        all_features[name] = series
    for name, series in max_drawdowns.items():
        all_features[name] = series
    
    # 替换 NaN 和 Inf
    all_features = all_features.replace([np.inf, -np.inf], np.nan)
    
    # 更新数据库
    logger.info(f"  更新数据库...")
    updated = 0
    
    for dt, row in all_features.iterrows():
        # 构建 UPDATE 语句
        set_clauses = []
        params = {'symbol_id': symbol_id}
        
        # 转换 pandas Timestamp 为 Python datetime 字符串 (包含微秒以匹配数据库格式)
        if hasattr(dt, 'strftime'):
            params['dt'] = dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        else:
            params['dt'] = str(dt)
        
        for col in all_features.columns:
            val = row[col]
            if pd.notna(val):
                set_clauses.append(f"{col} = :{col}")
                # 确保数值类型正确
                if isinstance(val, (np.integer, np.floating)):
                    params[col] = float(val)
                else:
                    params[col] = float(val)
        
        if not set_clauses:
            continue
        
        # 只更新存在的记录
        sql = f"""
            UPDATE attention_features 
            SET {', '.join(set_clauses)}
            WHERE symbol_id = :symbol_id 
            AND datetime = :dt
            AND timeframe = 'D'
        """
        
        try:
            result = session.execute(text(sql), params)
            if result.rowcount > 0:
                updated += 1
        except Exception as e:
            logger.error(f"    更新失败 {dt}: {e}")
    
    session.commit()
    return updated


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='回填预计算特征')
    parser.add_argument('--symbol', type=str, help='指定币种')
    parser.add_argument('--force', action='store_true', help='强制重新计算')
    parser.add_argument('--days', type=int, help='只处理最近 N 天')
    args = parser.parse_args()
    
    from src.config.settings import DATABASE_URL
    from src.database.models import Symbol, Price, AttentionFeature
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("\n" + "=" * 60)
    print("回填预计算特征")
    print("=" * 60)
    
    try:
        # 获取要处理的币种
        if args.symbol:
            symbols = session.query(Symbol).filter(Symbol.symbol == args.symbol.upper()).all()
        else:
            symbols = session.query(Symbol).filter(Symbol.auto_update_price == True).all()
        
        if not symbols:
            logger.warning("未找到需要处理的币种")
            return 1
        
        logger.info(f"将处理 {len(symbols)} 个币种")
        
        # 时间范围
        end_dt = datetime.now(timezone.utc)
        if args.days:
            start_dt = end_dt - timedelta(days=args.days)
        else:
            start_dt = datetime(2020, 1, 1, tzinfo=timezone.utc)
        
        total_updated = 0
        
        for sym in symbols:
            logger.info(f"\n处理 {sym.symbol}...")
            
            # 加载价格数据
            price_query = session.query(Price).filter(
                Price.symbol_id == sym.id,
                Price.timeframe == '1d',
                Price.datetime >= start_dt,
                Price.datetime <= end_dt
            ).order_by(Price.datetime)
            
            price_df = pd.DataFrame([{
                'datetime': p.datetime,
                'open': p.open,
                'high': p.high,
                'low': p.low,
                'close': p.close,
                'volume': p.volume
            } for p in price_query.all()])
            
            # 加载注意力数据
            att_query = session.query(AttentionFeature).filter(
                AttentionFeature.symbol_id == sym.id,
                AttentionFeature.timeframe == 'D',
                AttentionFeature.datetime >= start_dt,
                AttentionFeature.datetime <= end_dt
            ).order_by(AttentionFeature.datetime)
            
            attention_df = pd.DataFrame([{
                'datetime': a.datetime,
                'composite_attention_score': a.composite_attention_score,
                'composite_attention_zscore': a.composite_attention_zscore,
                'news_channel_score': a.news_channel_score,
                'google_trend_zscore': a.google_trend_zscore,
                'twitter_volume_zscore': a.twitter_volume_zscore,
                'bullish_attention': a.bullish_attention,
                'bearish_attention': a.bearish_attention,
            } for a in att_query.all()])
            
            updated = backfill_symbol(
                session, sym.symbol, sym.id,
                price_df, attention_df, args.force
            )
            
            logger.info(f"  {sym.symbol}: 更新了 {updated} 条记录")
            total_updated += updated
        
        print("\n" + "=" * 60)
        print(f"回填完成! 总共更新 {total_updated} 条记录")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"回填失败: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
