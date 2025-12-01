/**
 * 价格相关领域模型类型定义
 */

import { Timeframe } from './common';

/**
 * 单个价格点（K线数据）
 */
export interface PricePoint {
  timestamp: number;
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * 价格序列 - 带有计算好的统计摘要
 */
export interface PriceSeries {
  symbol: string;
  timeframe: Timeframe;
  points: PricePoint[];
  summary: PriceSeriesSummary;
}

/**
 * 价格序列统计摘要
 */
export interface PriceSeriesSummary {
  startDate: Date;
  endDate: Date;
  /** 跨越天数 */
  days: number;
  /** 区间最高价 */
  highPrice: number;
  /** 区间最低价 */
  lowPrice: number;
  /** 起始价格 */
  startPrice: number;
  /** 结束价格 */
  endPrice: number;
  /** 区间涨跌幅 */
  changePercent: number;
  /** 总成交量 */
  totalVolume: number;
  /** 平均成交量 */
  avgVolume: number;
}

/**
 * 成交量数据点
 */
export interface VolumePoint {
  timestamp: number;
  datetime: string;
  volume: number;
  /** 是否为上涨K线对应的成交量 */
  isUp: boolean;
}

/**
 * 实时价格数据
 */
export interface RealtimePriceData {
  timestamp: number;
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  /** 当前K线是否已收盘 */
  isClosed: boolean;
}

/**
 * 价格摘要统计（用于 SummaryCard）
 */
export interface PriceSummaryStats {
  currentPrice: number;
  priceChange24h: number;
  priceChange24hAbs: number;
  volume24h: number;
  high24h: number;
  low24h: number;
  volatility30d: number;
}

/**
 * 价格获取参数
 */
export interface FetchPriceParams {
  symbol: string;
  timeframe?: Timeframe;
  start?: string;
  end?: string;
  limit?: number;
}
