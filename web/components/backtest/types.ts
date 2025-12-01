/**
 * 回测模块内部类型定义
 */

import type { AttentionCondition } from '@/types/models/attention';

/**
 * 注意力源类型
 */
export type AttentionSource = 'legacy' | 'composite';

/**
 * 注意力条件源类型
 */
export type AttentionConditionSource = 'composite' | 'news_channel';

/**
 * 注意力区间类型
 */
export type AttentionRegime = 'low' | 'mid' | 'high' | 'custom';

/**
 * 回测面板参数状态
 */
export interface BacktestPanelParams {
  symbol: string;
  lookbackDays: number;
  attentionQuantile: number;
  maxDailyReturn: number;
  holdingDays: number;
  stopLossPct: number | null;
  takeProfitPct: number | null;
  maxHoldingDays: number | null;
  positionSize: number;
  attentionSource: AttentionSource;
}

/**
 * 注意力条件 UI 状态
 */
export interface AttentionConditionState {
  enabled: boolean;
  source: AttentionConditionSource;
  regime: AttentionRegime;
  lowerQuantile: number;
  upperQuantile: number;
  lookbackDays: number;
}

/**
 * 策略预设
 */
export interface LocalStrategyPreset {
  id: string;
  name: string;
  params: BacktestPanelParams;
  attentionCondition?: AttentionCondition | null;
  createdAt: string;
}

/**
 * 默认回测参数
 */
export const DEFAULT_BACKTEST_PARAMS: BacktestPanelParams = {
  symbol: 'ZECUSDT',
  lookbackDays: 30,
  attentionQuantile: 0.8,
  maxDailyReturn: 0.05,
  holdingDays: 3,
  stopLossPct: 0.05,
  takeProfitPct: 0.1,
  maxHoldingDays: 5,
  positionSize: 1.0,
  attentionSource: 'legacy',
};

/**
 * 默认注意力条件状态
 */
export const DEFAULT_ATTENTION_CONDITION: AttentionConditionState = {
  enabled: false,
  source: 'composite',
  regime: 'high',
  lowerQuantile: 0.8,
  upperQuantile: 1,
  lookbackDays: 30,
};
