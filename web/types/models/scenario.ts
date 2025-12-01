/**
 * 情景分析相关领域模型类型定义
 */

/**
 * 情景标签类型
 */
export type ScenarioLabel = 
  | 'trend_up' 
  | 'trend_down' 
  | 'spike_and_revert' 
  | 'crash' 
  | 'sideways';

/**
 * 情景摘要
 */
export interface ScenarioSummary {
  label: ScenarioLabel;
  description: string;
  sampleCount: number;
  probability: number;
  avgReturn3d?: number | null;
  avgReturn7d?: number | null;
  avgReturn30d?: number | null;
  maxDrawdown7d?: number | null;
  maxDrawdown30d?: number | null;
  avgPath?: number[] | null;
  sampleDetails?: any[] | null;
}

/**
 * 状态快照摘要
 */
export interface StateSnapshotSummary {
  symbol: string;
  asOf: string;
  timeframe: string;
  windowDays: number;
  features: Record<string, number>;
  rawStats: Record<string, any>;
}

/**
 * 情景分析响应
 */
export interface StateScenarioResponse {
  target: StateSnapshotSummary;
  scenarios: ScenarioSummary[];
  meta: {
    totalSimilarSamples: number;
    validSamplesAnalyzed: number;
    lookaheadDays: number[];
    message: string;
  };
}

/**
 * 情景分析参数
 */
export interface ScenarioAnalysisParams {
  symbol: string;
  timeframe?: string;
  windowDays?: number;
  topK?: number;
  maxHistoryDays?: number;
  includeSampleDetails?: boolean;
}

/**
 * 情景配置（UI 展示用）
 */
export interface ScenarioConfig {
  label: ScenarioLabel;
  displayName: string;
  icon: string;
  color: string;
  bgColor: string;
  borderColor: string;
}

/**
 * 情景配置映射
 */
export const SCENARIO_CONFIGS: Record<ScenarioLabel, Omit<ScenarioConfig, 'label'>> = {
  trend_up: {
    displayName: '趋势上行',
    icon: 'TrendingUp',
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-950/30',
    borderColor: 'border-green-200 dark:border-green-800',
  },
  trend_down: {
    displayName: '趋势下行',
    icon: 'TrendingDown',
    color: 'text-red-600 dark:text-red-400',
    bgColor: 'bg-red-50 dark:bg-red-950/30',
    borderColor: 'border-red-200 dark:border-red-800',
  },
  spike_and_revert: {
    displayName: '冲高回落',
    icon: 'Activity',
    color: 'text-yellow-600 dark:text-yellow-400',
    bgColor: 'bg-yellow-50 dark:bg-yellow-950/30',
    borderColor: 'border-yellow-200 dark:border-yellow-800',
  },
  crash: {
    displayName: '急剧下跌',
    icon: 'AlertTriangle',
    color: 'text-red-700 dark:text-red-500',
    bgColor: 'bg-red-100 dark:bg-red-950/50',
    borderColor: 'border-red-300 dark:border-red-700',
  },
  sideways: {
    displayName: '横盘震荡',
    icon: 'Minus',
    color: 'text-gray-600 dark:text-gray-400',
    bgColor: 'bg-gray-50 dark:bg-gray-800/50',
    borderColor: 'border-gray-200 dark:border-gray-700',
  },
};
