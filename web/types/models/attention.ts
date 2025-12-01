/**
 * 注意力相关领域模型类型定义
 */

/**
 * 注意力数据点
 */
export interface AttentionPoint {
  timestamp: number;
  datetime: string;
  /** 基础注意力分数 (0-100) */
  attentionScore: number;
  /** 新闻数量 */
  newsCount: number;
  /** 加权注意力 */
  weightedAttention?: number;
  /** 看多情绪注意力 */
  bullishAttention?: number;
  /** 看空情绪注意力 */
  bearishAttention?: number;
  /** 事件强度标记 */
  eventIntensity?: number;
  // Composite Attention 多通道字段
  /** 新闻渠道分数 */
  newsChannelScore?: number;
  /** Google Trends 值 */
  googleTrendValue?: number;
  /** Google Trends Z-Score */
  googleTrendZscore?: number;
  /** Twitter 成交量 */
  twitterVolume?: number;
  /** Twitter Z-Score */
  twitterVolumeZscore?: number;
  /** 综合注意力分数 */
  compositeAttentionScore?: number;
  /** 综合注意力 Z-Score */
  compositeAttentionZscore?: number;
  /** 综合注意力 Spike 标记 */
  compositeAttentionSpikeFlag?: number;
}

/**
 * 注意力序列
 */
export interface AttentionSeries {
  symbol: string;
  granularity: '1d';
  points: AttentionPoint[];
  summary: AttentionSeriesSummary;
}

/**
 * 注意力序列摘要
 */
export interface AttentionSeriesSummary {
  avgScore: number;
  maxScore: number;
  minScore: number;
  currentScore: number;
  trend: 'rising' | 'falling' | 'stable';
  spikeCount: number;
}

/**
 * 注意力事件类型
 */
export type AttentionEventType = 
  | 'attention_spike' 
  | 'high_weighted_event' 
  | 'high_bullish' 
  | 'high_bearish' 
  | 'event_intensity';

/**
 * 注意力事件
 */
export interface AttentionEvent {
  datetime: string;
  eventType: AttentionEventType;
  intensity: number;
  summary: string;
}

/**
 * 注意力 Regime 类型
 */
export type AttentionRegime = 'low' | 'mid' | 'high' | 'custom';

/**
 * 注意力 Regime 区间定义
 */
export interface RegimeSegment {
  regime: AttentionRegime;
  startDate: string;
  endDate: string;
  avgAttention: number;
}

/**
 * Regime 统计信息
 */
export interface RegimeStats {
  count: number;
  avgReturn: number;
  winRate: number;
  volatility: number;
  sharpe: number;
}

/**
 * 注意力条件（用于回测筛选）
 */
export interface AttentionCondition {
  source?: 'composite' | 'news_channel';
  regime?: AttentionRegime;
  operator?: 'gt' | 'lt' | 'gte' | 'lte';
  threshold?: number;
  metric?: 'attention_score' | 'composite_attention_score';
  lowerQuantile?: number;
  upperQuantile?: number;
  lookbackDays?: number;
}

/**
 * 注意力摘要统计
 */
export interface AttentionSummaryStats {
  currentAttention: number;
  avgAttention7d: number;
  avgAttention30d: number;
  newsCountToday: number;
  trend: 'rising' | 'falling' | 'stable';
}

/**
 * 注意力获取参数
 */
export interface FetchAttentionParams {
  symbol: string;
  granularity?: '1d';
  start?: string;
  end?: string;
}

/**
 * 注意力事件获取参数
 */
export interface FetchAttentionEventsParams {
  symbol: string;
  start?: string;
  end?: string;
  lookbackDays?: number;
  minQuantile?: number;
}
