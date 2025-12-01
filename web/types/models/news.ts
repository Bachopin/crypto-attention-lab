/**
 * 新闻相关领域模型类型定义
 */

/**
 * 新闻项
 */
export interface NewsItem {
  datetime: string;
  source: string;
  title: string;
  url: string;
  relevance?: string;
  sourceWeight?: number;
  sentimentScore?: number;
  tags?: string;
  symbols?: string;
  language?: string;
}

/**
 * 新闻趋势数据点
 */
export interface NewsTrendPoint {
  time: string;
  count: number;
  /** @deprecated 使用 attentionScore */
  attention: number;
  /** 标准化注意力分数 (0-100) */
  attentionScore: number;
  zScore: number;
  avgSentiment: number;
}

/**
 * 新闻趋势序列
 */
export interface NewsTrendSeries {
  symbol: string;
  interval: '1h' | '1d';
  points: NewsTrendPoint[];
}

/**
 * 新闻获取参数
 */
export interface FetchNewsParams {
  symbol?: string;
  start?: string;
  end?: string;
  limit?: number;
  before?: string;
  source?: string;
}

/**
 * 新闻趋势获取参数
 */
export interface FetchNewsTrendParams {
  symbol?: string;
  start?: string;
  end?: string;
  interval?: '1h' | '1d';
}

/**
 * 新闻统计摘要
 */
export interface NewsSummaryStats {
  totalCount: number;
  countToday: number;
  avgSentiment: number;
  topSources: { source: string; count: number }[];
}
