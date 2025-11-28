from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import logging

from src.data.db_storage import load_attention_data, load_price_data

logger = logging.getLogger(__name__)

def run_attention_rotation_backtest(
    symbols: List[str],
    attention_source: str = "composite",   # "composite" | "news_channel"
    rebalance_days: int = 7,              # 调仓周期
    lookback_days: int = 30,              # 计算 attention 排序用的回看窗口
    top_k: int = 3,                       # 每次持有的币数
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict:
    """
    多币种 Attention 轮动回测（v0 版本，等权多头组合）。

    - 在每个调仓日，对给定 symbol 池：
      - 计算过去 lookback_days 的 attention 指标（均值）；
      - 按该指标排序，选出前 top_k 个；
      - 下一个 rebalance_days 期间持有这些币，构成等权组合。
    - 输出整体组合的权益曲线、电梯式调仓信息，以及每次调仓的持仓列表。
    """
    
    # 1. 准备数据容器
    price_map = {}
    attention_map = {}
    
    # 确定 attention 列名
    if attention_source == "news_channel":
        att_col = "news_channel_score"
    else:
        # 默认 composite
        att_col = "composite_attention_score"
        
    # 2. 加载数据
    valid_symbols = []
    for sym in symbols:
        # 加载价格
        p_df, _ = load_price_data(sym, "1d", start, end)
        if p_df.empty:
            logger.warning(f"No price data for {sym}, skipping.")
            continue
            
        # 加载 Attention
        # 注意：load_attention_data 的 symbol 通常不带 USDT 后缀，这里做个简单处理
        base_sym = sym.replace("USDT", "")
        a_df = load_attention_data(base_sym, start, end)
        if a_df.empty:
            logger.warning(f"No attention data for {sym}, skipping.")
            continue
            
        if att_col not in a_df.columns:
            logger.warning(f"Column {att_col} not found for {sym}, skipping.")
            continue
            
        # 预处理：设置 datetime 索引
        p_df["datetime"] = pd.to_datetime(p_df["datetime"], utc=True)
        p_df = p_df.set_index("datetime").sort_index()
        
        a_df["datetime"] = pd.to_datetime(a_df["datetime"], utc=True)
        a_df = a_df.set_index("datetime").sort_index()
        
        # 对齐：只保留有价格和 Attention 的日期
        # 这里我们主要需要 Attention 来做决策，价格来计算收益
        # 简单起见，我们分别存储，但在计算时要注意对齐
        
        price_map[sym] = p_df["close"]
        attention_map[sym] = a_df[att_col]
        valid_symbols.append(sym)
        
    if not valid_symbols:
        return {"error": "No valid symbols found with both price and attention data."}
        
    # 3. 构建统一的时间轴
    # 取所有价格数据的并集时间轴，作为回测的主轴
    all_dates = sorted(list(set().union(*[p.index for p in price_map.values()])))
    if not all_dates:
        return {"error": "No common dates found."}
        
    full_idx = pd.DatetimeIndex(all_dates)
    
    # 将所有数据重采样/填充到统一时间轴
    prices_df = pd.DataFrame(index=full_idx)
    attentions_df = pd.DataFrame(index=full_idx)
    
    for sym in valid_symbols:
        # 价格使用 ffill 填充（停牌期间保持价格不变），但如果一开始没有数据则为 NaN
        prices_df[sym] = price_map[sym].reindex(full_idx).ffill()
        # Attention 也可以 ffill，或者填 0
        attentions_df[sym] = attention_map[sym].reindex(full_idx).ffill().fillna(0)
        
    # 计算日收益率
    returns_df = prices_df.pct_change().fillna(0)
    
    # 4. 回测循环
    # 从 lookback_days 之后开始
    if len(full_idx) <= lookback_days:
        return {"error": "Not enough data for lookback."}
        
    # 确定调仓日
    # 简单起见，从第 lookback_days 天开始，每隔 rebalance_days 调仓一次
    rebalance_dates = full_idx[lookback_days::rebalance_days]
    
    portfolio_equity = [1.0]
    portfolio_dates = [full_idx[lookback_days]] # 起始日
    
    rebalance_log = []
    
    current_equity = 1.0
    
    # 遍历每个调仓周期
    # 最后一个周期可能不完整，处理到数据结束
    
    # 我们需要遍历每一天来计算净值，或者分段计算
    # 为了生成每日净值曲线，我们按天遍历，但只在调仓日改变持仓
    
    current_holdings = [] # List of symbols
    
    # 初始化：在第一个调仓日之前，我们假设空仓或持有现金（净值不变），或者从第一个调仓日开始计算
    # 这里我们从第一个调仓日开始计算净值曲线
    
    # 实际上，rebalance_dates[0] 是第一个做出决策的日子。
    # 决策依据是 rebalance_dates[0] 之前的数据。
    # 持仓从 rebalance_dates[0] (收盘后/次日开盘) 开始生效。
    # 简化模型：在 rebalance_dates[0] 当天收盘时刻换仓，享受下一天的收益。
    
    # 让我们用一个更清晰的循环：
    # 每天检查是否是调仓日。如果是，更新持仓。
    # 然后应用当天的收益（基于昨天的持仓）。
    
    # 但要注意：第一天没有“昨天的持仓”。
    # 所以逻辑是：
    # Day T (Rebalance Day): Calculate signal, determine new holdings for T+1 onwards.
    # Day T+1: Apply return of new holdings.
    
    # 让我们定义：
    # rebalance_dates 是我们执行“选币”动作的日期。
    # 选出的币在 (date, next_rebalance_date] 区间内持有。
    
    # 为了方便，我们生成一个 daily_holdings map: date -> list of symbols
    daily_holdings = {}
    
    # 初始持仓为空
    current_symbols = []
    
    # 遍历所有交易日
    start_idx = lookback_days
    
    # 记录上一次调仓的日期索引
    last_rebalance_idx = -rebalance_days # 确保第一天能触发调仓（如果 start_idx 符合条件）
    
    # 实际上，我们可以直接在 rebalance_dates 循环
    # 但为了处理非调仓日的净值更新，我们需要知道每一天持有什么
    
    # 策略：
    # 1. 确定每个 rebalance date 的选币结果
    # 2. 将选币结果填充到下一个周期
    
    holdings_schedule = pd.Series(index=full_idx, dtype=object)
    
    for t_idx in range(start_idx, len(full_idx), rebalance_days):
        date = full_idx[t_idx]
        
        # 计算过去 lookback_days 的 attention 均值
        # 窗口: [date - lookback, date] (包含 date 当天的数据，假设收盘后拿到数据)
        # 或者 [date - lookback, date - 1] (避免未来函数，如果 date 是交易执行日)
        # 这里假设 date 是调仓日，利用 date 及之前的数据做决策，在 date 收盘时换仓
        
        # 切片：iloc[t_idx - lookback_days + 1 : t_idx + 1] -> 包含 t_idx
        window_data = attentions_df.iloc[t_idx - lookback_days + 1 : t_idx + 1]
        
        # 计算指标：均值
        scores = window_data.mean()
        
        # 排序
        # 过滤掉没有数据的 symbol (score=0 可能意味着没有数据，也可能是真的0，这里假设0是低分)
        # 如果需要过滤 NaN，前面已经 fillna(0) 了
        
        top_symbols = scores.sort_values(ascending=False).head(top_k).index.tolist()
        
        # 记录日志
        rebalance_log.append({
            "rebalance_date": date.isoformat(),
            "selected_symbols": top_symbols,
            "attention_values": scores[top_symbols].to_dict()
        })
        
        # 设置未来 rebalance_days 天的持仓 (包括今天收盘后的收益 -> 明天的收益)
        # 实际上，returns_df.loc[d] 是 d 当天的收益。
        # 如果我们在 d 日收盘换仓，那么 d+1 日的收益由新持仓决定。
        # 所以 holdings_schedule[d+1 ... d+rebalance] = top_symbols
        
        next_idx = min(t_idx + rebalance_days, len(full_idx))
        
        # 填充持仓
        # 注意：pandas 切片是左闭右开 (iloc) 或 左闭右闭 (loc)
        # 这里用 iloc 方便
        # 赋值给 t_idx + 1 到 next_idx (包含 next_idx 对应的日期，如果是最后一天)
        
        # 对应的日期范围
        dates_to_fill = full_idx[t_idx + 1 : next_idx + 1]
        for d in dates_to_fill:
            holdings_schedule[d] = top_symbols
            
    # 5. 计算净值曲线
    # 每天的组合收益 = 当天持仓 symbol 的收益平均值
    
    equity_curve = []
    current_equity = 1.0
    equity_curve.append({"datetime": full_idx[start_idx].isoformat(), "equity": current_equity})
    
    # 从 start_idx + 1 开始计算收益
    for i in range(start_idx + 1, len(full_idx)):
        date = full_idx[i]
        syms = holdings_schedule[date]
        
        if not isinstance(syms, list) or not syms:
            # 空仓
            daily_ret = 0.0
        else:
            # 获取这些 symbol 当天的收益
            # returns_df.loc[date, syms]
            # 注意：如果某个 symbol 当天停牌（收益0），则平均值会被拉低，这是合理的
            # 如果 symbol 还没上市（NaN），fillna(0) 处理了
            rets = returns_df.loc[date, syms]
            daily_ret = rets.mean()
            
        current_equity *= (1.0 + daily_ret)
        equity_curve.append({"datetime": date.isoformat(), "equity": current_equity})
        
    # 6. 计算统计指标
    # 转换为 Series 方便计算
    eq_series = pd.Series([e["equity"] for e in equity_curve])
    
    total_return = current_equity - 1.0
    
    # 年化收益
    days = (full_idx[-1] - full_idx[start_idx]).days
    if days > 0:
        annualized_return = (current_equity) ** (365 / days) - 1.0
    else:
        annualized_return = 0.0
        
    # 最大回撤
    cummax = eq_series.cummax()
    drawdown = (eq_series - cummax) / cummax
    max_drawdown = drawdown.min()
    
    # 波动率 (年化)
    # 计算日收益率序列
    pct_changes = eq_series.pct_change().dropna()
    volatility = pct_changes.std() * (365 ** 0.5)
    
    # 夏普比率 (假设无风险利率 0)
    if volatility > 0:
        sharpe = annualized_return / volatility
    else:
        sharpe = 0.0
        
    summary = {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "volatility": volatility,
        "sharpe": sharpe,
        "num_rebalances": len(rebalance_log),
        "start_date": full_idx[start_idx].isoformat(),
        "end_date": full_idx[-1].isoformat()
    }
    
    return {
        "params": {
            "symbols": symbols,
            "attention_source": attention_source,
            "rebalance_days": rebalance_days,
            "lookback_days": lookback_days,
            "top_k": top_k,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None
        },
        "equity_curve": equity_curve,
        "rebalance_log": rebalance_log,
        "summary": summary
    }
