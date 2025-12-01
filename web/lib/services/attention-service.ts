/**
 * 注意力服务层
 * 
 * 负责注意力数据、事件、Regime 分析的获取和转换
 */

import {
  fetchAttention as fetchAttentionApi,
  fetchAttentionEvents as fetchAttentionEventsApi,
  fetchAttentionRegimeAnalysis as fetchAttentionRegimeApi,
  FetchAttentionParams as ApiFetchAttentionParams,
  AttentionPoint as ApiAttentionPoint,
  AttentionEvent as ApiAttentionEvent,
  AttentionRegimeResponse as ApiAttentionRegimeResponse,
} from '@/lib/api';
import type {
  AttentionPoint,
  AttentionSeries,
  AttentionSeriesSummary,
  AttentionEvent,
  AttentionEventType,
  AttentionSummaryStats,
  RegimeStats,
} from '@/types/models/attention';

// ==================== 数据转换函数 ====================

/**
 * 将 API 返回的注意力点转换为领域模型
 */
function transformToAttentionPoint(apiPoint: ApiAttentionPoint): AttentionPoint {
  return {
    timestamp: apiPoint.timestamp,
    datetime: apiPoint.datetime,
    attentionScore: apiPoint.attention_score ?? 0,
    newsCount: apiPoint.news_count ?? 0,
    weightedAttention: apiPoint.weighted_attention,
    bullishAttention: apiPoint.bullish_attention,
    bearishAttention: apiPoint.bearish_attention,
    eventIntensity: apiPoint.event_intensity,
    newsChannelScore: apiPoint.news_channel_score,
    googleTrendValue: apiPoint.google_trend_value,
    googleTrendZscore: apiPoint.google_trend_zscore,
    twitterVolume: apiPoint.twitter_volume,
    twitterVolumeZscore: apiPoint.twitter_volume_zscore,
    compositeAttentionScore: apiPoint.composite_attention_score,
    compositeAttentionZscore: apiPoint.composite_attention_zscore,
    compositeAttentionSpikeFlag: apiPoint.composite_attention_spike_flag,
  };
}

/**
 * 将 API 返回的事件转换为领域模型
 */
function transformToAttentionEvent(apiEvent: ApiAttentionEvent): AttentionEvent {
  return {
    datetime: apiEvent.datetime,
    eventType: apiEvent.event_type as AttentionEventType,
    intensity: apiEvent.intensity,
    summary: apiEvent.summary,
  };
}

/**
 * 计算注意力序列的统计摘要
 */
function calculateAttentionSummary(points: AttentionPoint[]): AttentionSeriesSummary {
  if (points.length === 0) {
    return {
      avgScore: 0,
      maxScore: 0,
      minScore: 0,
      currentScore: 0,
      trend: 'stable',
      spikeCount: 0,
    };
  }

  // 优先使用 compositeAttentionScore，否则使用 attentionScore
  const scores = points.map(p => p.compositeAttentionScore ?? p.attentionScore);
  const avgScore = scores.reduce((sum, s) => sum + s, 0) / scores.length;
  const maxScore = Math.max(...scores);
  const minScore = Math.min(...scores);
  const currentScore = scores[scores.length - 1];

  // 计算趋势（比较最近 7 天与之前的平均）
  const recent7Days = scores.slice(-7);
  const earlier = scores.slice(-14, -7);
  let trend: 'rising' | 'falling' | 'stable' = 'stable';

  if (recent7Days.length > 0 && earlier.length > 0) {
    const recentAvg = recent7Days.reduce((sum, s) => sum + s, 0) / recent7Days.length;
    const earlierAvg = earlier.reduce((sum, s) => sum + s, 0) / earlier.length;
    if (recentAvg > earlierAvg * 1.1) trend = 'rising';
    else if (recentAvg < earlierAvg * 0.9) trend = 'falling';
  }

  // 计算 spike 数量
  const spikeCount = points.filter(p => p.compositeAttentionSpikeFlag === 1).length;

  return {
    avgScore,
    maxScore,
    minScore,
    currentScore,
    trend,
    spikeCount,
  };
}

/**
 * 将注意力数组转换为带统计的 AttentionSeries
 */
function transformToAttentionSeries(
  apiPoints: ApiAttentionPoint[],
  symbol: string
): AttentionSeries {
  const points = apiPoints.map(transformToAttentionPoint);
  const summary = calculateAttentionSummary(points);

  return {
    symbol,
    granularity: '1d',
    points,
    summary,
  };
}

// ==================== 服务函数 ====================

/**
 * 获取注意力数据
 */
export async function getAttentionData(
  symbol: string,
  options: { start?: string; end?: string } = {}
): Promise<AttentionSeries> {
  const apiPoints = await fetchAttentionApi({
    symbol,
    granularity: '1d',
    start: options.start,
    end: options.end,
  });

  return transformToAttentionSeries(apiPoints, symbol);
}

/**
 * 获取注意力事件
 */
export async function getAttentionEvents(
  symbol: string,
  options: { 
    start?: string; 
    end?: string; 
    lookbackDays?: number; 
    minQuantile?: number;
  } = {}
): Promise<AttentionEvent[]> {
  const { start, end, lookbackDays = 30, minQuantile = 0.8 } = options;

  const apiEvents = await fetchAttentionEventsApi({
    symbol,
    start,
    end,
    lookback_days: lookbackDays,
    min_quantile: minQuantile,
  });

  return apiEvents.map(transformToAttentionEvent);
}

/**
 * 获取注意力摘要统计（用于 Dashboard）
 */
export async function getAttentionSummaryStats(symbol: string): Promise<AttentionSummaryStats> {
  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

  try {
    const [weekData, monthData] = await Promise.all([
      fetchAttentionApi({ symbol, start: weekAgo.toISOString() }),
      fetchAttentionApi({ symbol, start: monthAgo.toISOString() }),
    ]);

    const weekPoints = weekData.map(transformToAttentionPoint);
    const monthPoints = monthData.map(transformToAttentionPoint);

    // 获取当前注意力
    const currentPoint = weekPoints[weekPoints.length - 1];
    const currentAttention = currentPoint
      ? (currentPoint.compositeAttentionScore ?? currentPoint.attentionScore ?? 0)
      : 0;

    // 计算 7 天和 30 天平均
    const getAvg = (points: AttentionPoint[]) => {
      if (points.length === 0) return 0;
      const scores = points.map(p => p.compositeAttentionScore ?? p.attentionScore);
      return scores.reduce((sum, s) => sum + s, 0) / scores.length;
    };

    const avgAttention7d = getAvg(weekPoints);
    const avgAttention30d = getAvg(monthPoints);

    // 今日新闻数（最后一个点）
    const newsCountToday = currentPoint?.newsCount ?? 0;

    // 计算趋势
    let trend: 'rising' | 'falling' | 'stable' = 'stable';
    if (currentAttention > avgAttention7d * 1.1) trend = 'rising';
    else if (currentAttention < avgAttention7d * 0.9) trend = 'falling';

    return {
      currentAttention,
      avgAttention7d,
      avgAttention30d,
      newsCountToday,
      trend,
    };
  } catch (error) {
    console.error('[AttentionService] Failed to get summary stats:', error);
    return {
      currentAttention: 0,
      avgAttention7d: 0,
      avgAttention30d: 0,
      newsCountToday: 0,
      trend: 'stable',
    };
  }
}

/**
 * 获取注意力 Regime 分析
 */
export async function getAttentionRegimeAnalysis(
  symbols: string[],
  options: {
    lookaheadDays?: number[];
    attentionSource?: 'composite' | 'news_channel' | 'google_channel' | 'twitter_channel';
    splitMethod?: 'tercile' | 'quartile';
    start?: string;
    end?: string;
  } = {}
): Promise<{
  params: any;
  results: Record<string, RegimeStats>;
  meta: {
    lookaheadDays: number[];
    message?: string;
  };
}> {
  const response = await fetchAttentionRegimeApi({
    symbols,
    lookahead_days: options.lookaheadDays ?? [7, 30],
    attention_source: options.attentionSource ?? 'composite',
    split_method: options.splitMethod ?? 'tercile',
    start: options.start,
    end: options.end,
  });

  // 转换响应格式
  return {
    params: response.params,
    results: response.results,
    meta: {
      lookaheadDays: response.meta.lookahead_days,
      message: response.meta.message,
    },
  };
}

/**
 * 将 Z-Score 转换为 0-100 的注意力分数
 */
export function zScoreToAttentionScore(zScore: number): number {
  // 转换公式：mean 50, std ~15
  return Math.max(0, Math.min(100, 50 + zScore * 15));
}

/**
 * 将 0-100 的注意力分数转换为 Z-Score
 */
export function attentionScoreToZScore(score: number): number {
  return (score - 50) / 15;
}

// ==================== 导出 ====================

export const attentionService = {
  getAttentionData,
  getAttentionEvents,
  getAttentionSummaryStats,
  getAttentionRegimeAnalysis,
  zScoreToAttentionScore,
  attentionScoreToZScore,
  // 转换函数
  transformToAttentionPoint,
  transformToAttentionEvent,
  transformToAttentionSeries,
};

export default attentionService;
