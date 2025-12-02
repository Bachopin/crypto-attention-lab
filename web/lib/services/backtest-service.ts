/**
 * 回测服务层
 * 
 * 负责回测执行、结果转换和策略管理
 */

import {
  runBasicAttentionBacktest as runBacktestApi,
  runMultiSymbolBacktest as runMultiBacktestApi,
  fetchAttentionEventPerformance as fetchEventPerformanceApi,
  runAttentionRotationBacktest as runRotationBacktestApi,
  BacktestResult as ApiBacktestResult,
  MultiBacktestResult as ApiMultiBacktestResult,
  EventPerformanceTable as ApiEventPerformanceTable,
  AttentionRotationResult as ApiAttentionRotationResult,
  AttentionCondition as ApiAttentionCondition,
} from '@/lib/api';
import type {
  BacktestParams,
  BacktestResult,
  BacktestSummary,
  MultiBacktestResult,
  Trade,
  EquityPoint,
  StrategyPreset,
  EventPerformanceRow,
  EventPerformanceTable,
  AttentionRotationParams,
  AttentionRotationResult,
} from '@/types/models/backtest';
import type { AttentionCondition } from '@/types/models/attention';

// ==================== 数据转换函数 ====================

/**
 * 将 API 返回的交易记录转换为领域模型
 */
function transformTrade(apiTrade: any): Trade {
  return {
    entryDate: apiTrade.entry_date,
    exitDate: apiTrade.exit_date,
    entryPrice: apiTrade.entry_price,
    exitPrice: apiTrade.exit_price,
    returnPct: apiTrade.return_pct,
    holdingDays: apiTrade.holding_days,
    reason: apiTrade.reason,
    symbol: apiTrade.symbol,
  };
}

/**
 * 将 API 返回的权益曲线点转换为领域模型
 */
function transformEquityPoint(apiPoint: any): EquityPoint {
  return {
    date: apiPoint.date || apiPoint.datetime,
    datetime: apiPoint.datetime,
    equity: apiPoint.equity,
    drawdown: apiPoint.drawdown,
    price: apiPoint.price,
    benchmark: apiPoint.benchmark,
  };
}

/**
 * 将 API 返回的回测摘要转换为领域模型
 */
function transformBacktestSummary(apiSummary: any): BacktestSummary {
  return {
    totalReturn: apiSummary.total_return,
    cumulativeReturn: apiSummary.cumulative_return ?? apiSummary.total_return,
    annualizedReturn: apiSummary.annualized_return,
    maxDrawdown: apiSummary.max_drawdown,
    winRate: apiSummary.win_rate,
    totalTrades: apiSummary.total_trades,
    sharpeRatio: apiSummary.sharpe_ratio,
    avgReturn: apiSummary.avg_return,
    avgTradeReturn: apiSummary.avg_trade_return,
    attentionCondition: apiSummary.attention_condition
      ? transformAttentionCondition(apiSummary.attention_condition)
      : undefined,
    error: apiSummary.error,
  };
}

/**
 * 将 API 返回的注意力条件转换为领域模型
 */
function transformAttentionCondition(apiCondition: ApiAttentionCondition): AttentionCondition {
  return {
    source: apiCondition.source as 'composite' | 'news_channel',
    regime: apiCondition.regime as any,
    operator: apiCondition.operator,
    threshold: apiCondition.threshold,
    metric: apiCondition.metric,
    lowerQuantile: apiCondition.lower_quantile,
    upperQuantile: apiCondition.upper_quantile,
    lookbackDays: apiCondition.lookback_days,
  };
}

/**
 * 将领域模型的注意力条件转换为 API 格式
 */
function toApiAttentionCondition(condition: AttentionCondition | null | undefined): ApiAttentionCondition | null {
  if (!condition) return null;
  
  return {
    source: condition.source,
    regime: condition.regime,
    operator: condition.operator,
    threshold: condition.threshold,
    metric: condition.metric,
    lower_quantile: condition.lowerQuantile,
    upper_quantile: condition.upperQuantile,
    lookback_days: condition.lookbackDays,
  };
}

/**
 * 将 API 返回的回测结果转换为领域模型
 */
function transformBacktestResult(apiResult: ApiBacktestResult): BacktestResult {
  const safeEquity = Array.isArray((apiResult as any).equity_curve) ? (apiResult as any).equity_curve : [];
  const safeTrades = Array.isArray((apiResult as any).trades) ? (apiResult as any).trades : [];

  return {
    params: (apiResult as any).params,
    meta: (apiResult as any).meta ? {
      attentionSource: (apiResult as any).meta.attention_source,
      signalField: (apiResult as any).meta.signal_field,
      attentionCondition: (apiResult as any).meta.attention_condition
        ? transformAttentionCondition((apiResult as any).meta.attention_condition)
        : undefined,
    } : undefined,
    equityCurve: safeEquity.map(transformEquityPoint),
    trades: safeTrades.map(transformTrade),
    summary: transformBacktestSummary((apiResult as any).summary || {}),
  };
}

/**
 * 将 API 返回的多币种回测结果转换为领域模型
 */
function transformMultiBacktestResult(apiResult: ApiMultiBacktestResult): MultiBacktestResult {
  const perSymbolSummary: Record<string, BacktestSummary> = {};
  const perSymbolTrades: Record<string, Trade[]> = {};
  const perSymbolEquityCurves: Record<string, EquityPoint[]> = {};

  Object.entries(apiResult.per_symbol_summary).forEach(([symbol, summary]) => {
    perSymbolSummary[symbol] = transformBacktestSummary(summary);
  });

  if (apiResult.per_symbol_trades) {
    Object.entries(apiResult.per_symbol_trades).forEach(([symbol, trades]) => {
      const safe = Array.isArray(trades) ? trades : [];
      perSymbolTrades[symbol] = safe.map(transformTrade);
    });
  }

  if (apiResult.per_symbol_equity_curves) {
    Object.entries(apiResult.per_symbol_equity_curves).forEach(([symbol, curve]) => {
      perSymbolEquityCurves[symbol] = curve.map(transformEquityPoint);
    });
  }

  return {
    params: { ...apiResult.params, symbols: apiResult.params.symbols },
    meta: apiResult.meta ? {
      attentionSource: apiResult.meta.attention_source,
    } : undefined,
    aggregateSummary: transformBacktestSummary((apiResult as any).aggregate_summary || {}),
    aggregateEquityCurve: Array.isArray((apiResult as any).aggregate_equity_curve)
      ? (apiResult as any).aggregate_equity_curve.map(transformEquityPoint)
      : [],
    perSymbolSummary,
    perSymbolTrades,
    perSymbolEquityCurves,
    perSymbolMeta: apiResult.per_symbol_meta,
  };
}

// ==================== 服务函数 ====================

/**
 * 执行单币种回测
 */
export async function runBacktest(params: BacktestParams): Promise<BacktestResult> {
  const apiResult = await runBacktestApi({
    symbol: params.symbol,
    lookback_days: params.lookbackDays,
    attention_quantile: params.attentionQuantile,
    max_daily_return: params.maxDailyReturn,
    holding_days: params.holdingDays,
    stop_loss_pct: params.stopLossPct,
    take_profit_pct: params.takeProfitPct,
    max_holding_days: params.maxHoldingDays,
    position_size: params.positionSize,
    attention_source: params.attentionSource,
    attention_condition: toApiAttentionCondition(params.attentionCondition),
    start: params.start,
    end: params.end,
  });

  return transformBacktestResult(apiResult);
}

/**
 * 执行多币种回测
 */
export async function runMultiBacktest(
  symbols: string[],
  params: Omit<BacktestParams, 'symbol'>
): Promise<MultiBacktestResult> {
  const apiResult = await runMultiBacktestApi({
    symbols,
    lookback_days: params.lookbackDays,
    attention_quantile: params.attentionQuantile,
    max_daily_return: params.maxDailyReturn,
    holding_days: params.holdingDays,
    stop_loss_pct: params.stopLossPct,
    take_profit_pct: params.takeProfitPct,
    max_holding_days: params.maxHoldingDays,
    position_size: params.positionSize,
    attention_source: params.attentionSource,
    attention_condition: toApiAttentionCondition(params.attentionCondition),
    start: params.start,
    end: params.end,
  });

  return transformMultiBacktestResult(apiResult);
}

/**
 * 执行注意力轮动回测
 */
export async function runAttentionRotationBacktest(
  params: AttentionRotationParams
): Promise<AttentionRotationResult> {
  const apiResult = await runRotationBacktestApi({
    symbols: params.symbols,
    attention_source: params.attentionSource,
    rebalance_days: params.rebalanceDays,
    lookback_days: params.lookbackDays,
    top_k: params.topK,
    start: params.start,
    end: params.end,
  });

  return {
    params: {
      symbols: apiResult.params.symbols,
      attentionSource: apiResult.params.attention_source as 'composite' | 'news_channel',
      rebalanceDays: apiResult.params.rebalance_days,
      lookbackDays: apiResult.params.lookback_days,
      topK: apiResult.params.top_k,
      start: apiResult.params.start,
      end: apiResult.params.end,
    },
    equityCurve: apiResult.equity_curve.map(transformEquityPoint),
    rebalanceLog: apiResult.rebalance_log.map(log => ({
      rebalanceDate: log.rebalance_date,
      selectedSymbols: log.selected_symbols,
      attentionValues: log.attention_values,
    })),
    summary: {
      totalReturn: apiResult.summary.total_return,
      annualizedReturn: apiResult.summary.annualized_return,
      maxDrawdown: apiResult.summary.max_drawdown,
      volatility: apiResult.summary.volatility,
      sharpe: apiResult.summary.sharpe,
      numRebalances: apiResult.summary.num_rebalances,
      startDate: apiResult.summary.start_date,
      endDate: apiResult.summary.end_date,
    },
  };
}

/**
 * 获取事件表现分析
 * 
 * 后端返回格式: {event_type: {lookahead_days: {...}, ...}, ...}
 * 需要转换为前端期望的表格格式
 */
export async function getEventPerformance(
  symbol: string,
  lookaheadDays: string = '1,3,5,10'
): Promise<EventPerformanceTable> {
  // 后端期望不带 USDT 后缀的 symbol
  const cleanSymbol = symbol.replace(/USDT$/i, '').toUpperCase();
  const apiResult = await fetchEventPerformanceApi({ symbol: cleanSymbol, lookahead_days: lookaheadDays });

  // 转换后端格式为前端表格行格式
  // 后端: {event_type: {'1': {avg_return, sample_size}, '3': {...}, ...}}
  // 前端: {rows: [{eventType, count, avgReturn1d, avgReturn3d, ...}]}
  const rows: EventPerformanceRow[] = [];
  
  for (const [eventType, horizons] of Object.entries(apiResult)) {
    const horizonData = horizons as Record<string, { avg_return: number; sample_size: number }>;
    
    // 取第一个 horizon 的 sample_size 作为 count（所有 horizon 应该相同）
    const firstHorizon = Object.values(horizonData)[0];
    const count = firstHorizon?.sample_size || 0;
    
    rows.push({
      eventType,
      count,
      avgReturn1d: horizonData['1']?.avg_return || 0,
      avgReturn3d: horizonData['3']?.avg_return || 0,
      avgReturn5d: horizonData['5']?.avg_return || 0,
      avgReturn10d: horizonData['10']?.avg_return || 0,
      // 后端暂不提供 win rate，设为 0
      winRate1d: 0,
      winRate3d: 0,
      winRate5d: 0,
      winRate10d: 0,
    });
  }

  return {
    symbol: cleanSymbol,
    updatedAt: new Date().toISOString(),
    rows,
  };
}

/**
 * 创建默认回测参数
 */
export function createDefaultBacktestParams(
  symbol: string,
  overrides: Partial<BacktestParams> = {}
): BacktestParams {
  return {
    symbol: symbol.endsWith('USDT') ? symbol : `${symbol}USDT`,
    lookbackDays: 30,
    attentionQuantile: 0.8,
    maxDailyReturn: 0.05,
    holdingDays: 3,
    stopLossPct: 0.05,
    takeProfitPct: 0.1,
    maxHoldingDays: 5,
    positionSize: 1.0,
    attentionSource: 'legacy',
    ...overrides,
  };
}

/**
 * 格式化注意力条件摘要（用于 UI 显示）
 */
export function formatConditionSummary(condition: AttentionCondition | null | undefined): string {
  if (!condition) return '—';
  
  const source = condition.source === 'composite' ? 'Composite' : 'News Channel';
  let regimeLabel: string = condition.regime || 'unknown';
  
  if (condition.regime === 'custom') {
    const l = condition.lowerQuantile ?? 0;
    const u = condition.upperQuantile ?? 1;
    regimeLabel = `custom(${(l * 100).toFixed(0)}%-${(u * 100).toFixed(0)}%)`;
  }
  
  return `${source}, ${regimeLabel}, ${condition.lookbackDays}d`;
}

// ==================== 导出 ====================

export const backtestService = {
  runBacktest,
  runMultiBacktest,
  runAttentionRotationBacktest,
  getEventPerformance,
  createDefaultBacktestParams,
  formatConditionSummary,
  // 转换函数
  transformBacktestResult,
  transformMultiBacktestResult,
  transformTrade,
  transformEquityPoint,
};

export default backtestService;
