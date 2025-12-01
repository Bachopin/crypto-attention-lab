/**
 * Scenario Service
 * 
 * 情景分析服务层 - 封装情景/相似状态/快照相关的业务逻辑
 */

import { fetchStateScenarios } from '@/lib/api';

import type {
  ScenarioSummary,
  StateSnapshotSummary,
  StateScenarioResponse,
} from '@/types/models';

// ============================================================
// Service Types
// ============================================================

/** 情景标签类型 */
export type ScenarioLabel = 
  | 'trend_up' 
  | 'trend_down' 
  | 'spike_and_revert' 
  | 'crash' 
  | 'sideways';

export interface ScenarioSearchParams {
  symbol: string;
  timeframe?: string;
  windowDays?: number;
  topK?: number;
  maxHistoryDays?: number;
  includeSampleDetails?: boolean;
}

export interface ScenarioAnalysisResult {
  target: StateSnapshotSummary;
  scenarios: ScenarioSummary[];
  meta: {
    totalSimilarSamples: number;
    validSamplesAnalyzed: number;
    lookaheadDays: number[];
    message: string;
  };
}

// ============================================================
// Service Implementation
// ============================================================

class ScenarioService {
  /**
   * 获取完整的情景分析（包括目标状态快照和所有情景）
   */
  async getScenarioAnalysis(
    params: ScenarioSearchParams
  ): Promise<ScenarioAnalysisResult> {
    const {
      symbol,
      timeframe = '1d',
      windowDays = 30,
      topK = 100,
      maxHistoryDays = 365,
      includeSampleDetails = false,
    } = params;

    const response = await fetchStateScenarios({
      symbol,
      timeframe,
      window_days: windowDays,
      top_k: topK,
      max_history_days: maxHistoryDays,
      include_sample_details: includeSampleDetails,
    });

    return this.transformResponse(response);
  }

  /**
   * 仅获取情景列表
   */
  async getScenarios(params: ScenarioSearchParams): Promise<ScenarioSummary[]> {
    const result = await this.getScenarioAnalysis(params);
    return result.scenarios;
  }

  /**
   * 获取当前状态快照
   */
  async getCurrentSnapshot(
    symbol: string,
    timeframe: string = '1d'
  ): Promise<StateSnapshotSummary> {
    const result = await this.getScenarioAnalysis({ symbol, timeframe });
    return result.target;
  }

  /**
   * 按 label 过滤情景
   */
  async getScenariosByLabel(
    params: ScenarioSearchParams,
    labels: ScenarioLabel[]
  ): Promise<ScenarioSummary[]> {
    const scenarios = await this.getScenarios(params);
    return scenarios.filter((s) => labels.includes(s.label as ScenarioLabel));
  }

  /**
   * 获取最可能的情景
   */
  async getMostLikelyScenario(
    symbol: string
  ): Promise<ScenarioSummary | null> {
    const scenarios = await this.getScenarios({ symbol });
    if (scenarios.length === 0) return null;
    
    // 按概率排序
    return scenarios.reduce((best, current) => 
      current.probability > best.probability ? current : best
    );
  }

  /**
   * 获取看涨/看跌情景
   */
  async getBullishBearishScenarios(
    symbol: string
  ): Promise<{
    bullish: ScenarioSummary[];
    bearish: ScenarioSummary[];
    neutral: ScenarioSummary[];
  }> {
    const scenarios = await this.getScenarios({ symbol });
    
    return {
      bullish: scenarios.filter((s) => s.label === 'trend_up'),
      bearish: scenarios.filter((s) => 
        s.label === 'trend_down' || s.label === 'crash'
      ),
      neutral: scenarios.filter((s) => 
        s.label === 'sideways' || s.label === 'spike_and_revert'
      ),
    };
  }

  // ============================================================
  // Transform Helpers
  // ============================================================

  private transformResponse(response: StateScenarioResponse): ScenarioAnalysisResult {
    return {
      target: response.target,
      scenarios: response.scenarios,
      meta: {
        totalSimilarSamples: response.meta.total_similar_samples,
        validSamplesAnalyzed: response.meta.valid_samples_analyzed,
        lookaheadDays: response.meta.lookahead_days,
        message: response.meta.message,
      },
    };
  }

  /**
   * 将 ScenarioLabel 转换为中文显示名
   */
  getLabelDisplayName(label: ScenarioLabel): string {
    const names: Record<ScenarioLabel, string> = {
      trend_up: '趋势上行',
      trend_down: '趋势下行',
      spike_and_revert: '冲高回落',
      crash: '急剧下跌',
      sideways: '横盘震荡',
    };
    return names[label] ?? label;
  }

  /**
   * 获取 label 对应的颜色类名
   */
  getLabelColorClass(label: ScenarioLabel): string {
    const colors: Record<ScenarioLabel, string> = {
      trend_up: 'text-green-600 dark:text-green-400',
      trend_down: 'text-red-600 dark:text-red-400',
      spike_and_revert: 'text-yellow-600 dark:text-yellow-400',
      crash: 'text-red-700 dark:text-red-500',
      sideways: 'text-gray-600 dark:text-gray-400',
    };
    return colors[label] ?? 'text-gray-500';
  }

  /**
   * 格式化概率显示
   */
  formatProbability(probability: number): string {
    return `${(probability * 100).toFixed(1)}%`;
  }

  /**
   * 格式化回报率显示
   */
  formatReturn(returnValue: number | null | undefined): string {
    if (returnValue == null) return '-';
    const sign = returnValue >= 0 ? '+' : '';
    return `${sign}${(returnValue * 100).toFixed(2)}%`;
  }
}

// ============================================================
// Export singleton instance
// ============================================================

export const scenarioService = new ScenarioService();
