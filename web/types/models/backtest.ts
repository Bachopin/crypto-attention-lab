/**
 * 回测相关领域模型类型定义
 */

import { AttentionCondition } from './attention';

/**
 * 权益曲线数据点
 */
export interface EquityPoint {
  date: string;
  datetime: string;
  equity: number;
  drawdown: number;
  price?: number;
  benchmark?: number;
}

/**
 * 交易记录
 */
export interface Trade {
  entryDate: string;
  exitDate: string;
  entryPrice: number;
  exitPrice: number;
  returnPct: number;
  holdingDays: number;
  reason: string;
  symbol?: string;
}

/**
 * 回测摘要统计
 */
export interface BacktestSummary {
  totalReturn: number;
  cumulativeReturn: number;
  annualizedReturn: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  sharpeRatio: number;
  avgReturn: number;
  avgTradeReturn?: number;
  attentionCondition?: AttentionCondition;
  error?: string;
}

/**
 * 回测参数
 */
export interface BacktestParams {
  symbol: string;
  lookbackDays: number;
  attentionQuantile: number;
  maxDailyReturn: number;
  holdingDays: number;
  stopLossPct: number | null;
  takeProfitPct: number | null;
  maxHoldingDays: number | null;
  positionSize: number;
  attentionSource: 'legacy' | 'composite';
  attentionCondition?: AttentionCondition | null;
  start?: string;
  end?: string;
}

/**
 * 回测结果
 */
export interface BacktestResult {
  params: BacktestParams;
  meta?: {
    attentionSource?: string;
    signalField?: string;
    attentionCondition?: AttentionCondition;
  };
  equityCurve: EquityPoint[];
  trades: Trade[];
  summary: BacktestSummary;
}

/**
 * 多币种回测结果
 */
export interface MultiBacktestResult {
  params: BacktestParams & { symbols: string[] };
  meta?: {
    attentionSource?: string;
  };
  aggregateSummary: BacktestSummary;
  aggregateEquityCurve: EquityPoint[];
  perSymbolSummary: Record<string, BacktestSummary>;
  perSymbolTrades: Record<string, Trade[]>;
  perSymbolEquityCurves?: Record<string, EquityPoint[]>;
  perSymbolMeta?: Record<string, any>;
}

/**
 * 策略预设
 */
export interface StrategyPreset {
  id: string;
  name: string;
  description: string;
  attentionCondition?: AttentionCondition;
  params: Partial<BacktestParams>;
}

/**
 * 注意力轮动回测参数
 */
export interface AttentionRotationParams {
  symbols: string[];
  attentionSource: 'composite' | 'news_channel';
  rebalanceDays: number;
  lookbackDays: number;
  topK: number;
  start?: string;
  end?: string;
}

/**
 * 注意力轮动回测结果
 */
export interface AttentionRotationResult {
  params: AttentionRotationParams;
  equityCurve: EquityPoint[];
  rebalanceLog: {
    rebalanceDate: string;
    selectedSymbols: string[];
    attentionValues: Record<string, number>;
  }[];
  summary: {
    totalReturn: number;
    annualizedReturn: number;
    maxDrawdown: number;
    volatility: number;
    sharpe: number;
    numRebalances: number;
    startDate: string;
    endDate: string;
  };
}

/**
 * 事件表现统计行
 */
export interface EventPerformanceRow {
  eventType: string;
  count: number;
  avgReturn1d: number;
  avgReturn3d: number;
  avgReturn5d: number;
  avgReturn10d: number;
  winRate1d: number;
  winRate3d: number;
  winRate5d: number;
  winRate10d: number;
}

/**
 * 事件表现表格
 */
export interface EventPerformanceTable {
  symbol: string;
  updatedAt: string;
  rows: EventPerformanceRow[];
}
