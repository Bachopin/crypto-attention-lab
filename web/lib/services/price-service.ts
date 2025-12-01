/**
 * 价格服务层
 * 
 * 负责价格数据的获取、转换和统计计算
 * 组件通过此服务获取数据，而不是直接调用 API
 */

import {
  fetchPrice as fetchPriceApi,
  fetchSummaryStats as fetchSummaryStatsApi,
  FetchPriceParams,
  Candle,
} from '@/lib/api';
import type {
  PricePoint,
  PriceSeries,
  PriceSeriesSummary,
  PriceSummaryStats,
  VolumePoint,
  Timeframe,
} from '@/types/models/index';

// ==================== 数据转换函数 ====================

/**
 * 将 API 返回的 Candle 转换为领域模型 PricePoint
 */
function transformCandleToPricePoint(candle: Candle): PricePoint {
  return {
    timestamp: candle.timestamp,
    datetime: candle.datetime,
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
    volume: candle.volume,
  };
}

/**
 * 计算价格序列的统计摘要
 */
function calculatePriceSeriesSummary(points: PricePoint[]): PriceSeriesSummary {
  if (points.length === 0) {
    return {
      startDate: new Date(),
      endDate: new Date(),
      days: 0,
      highPrice: 0,
      lowPrice: 0,
      startPrice: 0,
      endPrice: 0,
      changePercent: 0,
      totalVolume: 0,
      avgVolume: 0,
    };
  }

  const startPrice = points[0].open;
  const endPrice = points[points.length - 1].close;
  const highPrice = Math.max(...points.map(p => p.high));
  const lowPrice = Math.min(...points.map(p => p.low));
  const totalVolume = points.reduce((sum, p) => sum + p.volume, 0);

  const startDate = new Date(points[0].timestamp);
  const endDate = new Date(points[points.length - 1].timestamp);
  const days = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));

  return {
    startDate,
    endDate,
    days,
    highPrice,
    lowPrice,
    startPrice,
    endPrice,
    changePercent: startPrice > 0 ? ((endPrice - startPrice) / startPrice) * 100 : 0,
    totalVolume,
    avgVolume: points.length > 0 ? totalVolume / points.length : 0,
  };
}

/**
 * 将 Candle 数组转换为带统计的 PriceSeries
 */
function transformToPriceSeries(
  candles: Candle[],
  symbol: string,
  timeframe: Timeframe
): PriceSeries {
  const points = candles.map(transformCandleToPricePoint);
  const summary = calculatePriceSeriesSummary(points);

  return {
    symbol,
    timeframe,
    points,
    summary,
  };
}

/**
 * 提取成交量数据
 */
function extractVolumePoints(points: PricePoint[]): VolumePoint[] {
  return points.map(p => ({
    timestamp: p.timestamp,
    datetime: p.datetime,
    volume: p.volume,
    isUp: p.close >= p.open,
  }));
}

// ==================== 服务函数 ====================

/**
 * 获取价格数据并转换为领域模型
 */
export async function getPriceData(
  symbol: string,
  timeframe: Timeframe = '1D',
  options: { start?: string; end?: string; limit?: number } = {}
): Promise<PriceSeries> {
  const { start, end, limit } = options;
  
  // 确保 symbol 带有 USDT 后缀
  const tradingPair = symbol.endsWith('USDT') ? symbol : `${symbol}USDT`;
  
  const candles = await fetchPriceApi({
    symbol: tradingPair,
    timeframe,
    start,
    end,
    limit,
  });

  if (!candles || candles.length === 0) {
    throw new Error(`No price data available for ${symbol}`);
  }

  return transformToPriceSeries(candles, symbol, timeframe);
}

/**
 * 获取价格概览数据（用于 Overview 图表）
 * 默认获取最近 1000 根 1D K线
 */
export async function getPriceOverview(symbol: string): Promise<PriceSeries> {
  return getPriceData(symbol, '1D', { limit: 1000 });
}

/**
 * 获取最近价格数据（用于主图表）
 * 根据时间周期返回合适数量的数据
 */
export async function getRecentPriceData(
  symbol: string,
  timeframe: Timeframe = '1D',
  limit: number = 300
): Promise<PriceSeries> {
  return getPriceData(symbol, timeframe, { limit });
}

/**
 * 获取成交量数据
 */
export async function getVolumeData(
  symbol: string,
  timeframe: Timeframe = '1D',
  options: { start?: string; end?: string; limit?: number } = {}
): Promise<VolumePoint[]> {
  const priceSeries = await getPriceData(symbol, timeframe, options);
  return extractVolumePoints(priceSeries.points);
}

/**
 * 获取价格摘要统计（用于 StatCards）
 */
export async function getPriceSummaryStats(symbol: string): Promise<PriceSummaryStats> {
  try {
    const stats = await fetchSummaryStatsApi(symbol);
    
    return {
      currentPrice: stats.current_price,
      priceChange24h: stats.price_change_24h,
      priceChange24hAbs: stats.price_change_24h_abs,
      volume24h: stats.volume_24h,
      high24h: 0, // 如果 API 不提供，可以从价格数据计算
      low24h: 0,
      volatility30d: stats.volatility_30d,
    };
  } catch (error) {
    console.error('[PriceService] Failed to get summary stats:', error);
    
    // 返回默认值而不是抛出错误
    return {
      currentPrice: 0,
      priceChange24h: 0,
      priceChange24hAbs: 0,
      volume24h: 0,
      high24h: 0,
      low24h: 0,
      volatility30d: 0,
    };
  }
}

/**
 * 计算指定时间范围的价格变化
 */
export function calculatePriceChange(
  points: PricePoint[],
  days: number = 1
): { changePercent: number; changeAbs: number } {
  if (points.length < 2) {
    return { changePercent: 0, changeAbs: 0 };
  }

  // 假设每个点是一天（对于 1D 周期）
  const startIndex = Math.max(0, points.length - days - 1);
  const startPrice = points[startIndex].close;
  const endPrice = points[points.length - 1].close;

  const changeAbs = endPrice - startPrice;
  const changePercent = startPrice > 0 ? (changeAbs / startPrice) * 100 : 0;

  return { changePercent, changeAbs };
}

/**
 * 计算波动率（基于日收益率的标准差）
 */
export function calculateVolatility(points: PricePoint[], days: number = 30): number {
  if (points.length < 2) return 0;

  const recentPoints = points.slice(-days);
  const returns: number[] = [];

  for (let i = 1; i < recentPoints.length; i++) {
    const prevClose = recentPoints[i - 1].close;
    if (prevClose > 0) {
      returns.push((recentPoints[i].close - prevClose) / prevClose);
    }
  }

  if (returns.length === 0) return 0;

  // 计算标准差
  const mean = returns.reduce((sum, r) => sum + r, 0) / returns.length;
  const squaredDiffs = returns.map(r => Math.pow(r - mean, 2));
  const variance = squaredDiffs.reduce((sum, d) => sum + d, 0) / returns.length;

  return Math.sqrt(variance) * 100; // 返回百分比
}

// ==================== 导出 ====================

export const priceService = {
  getPriceData,
  getPriceOverview,
  getRecentPriceData,
  getVolumeData,
  getPriceSummaryStats,
  calculatePriceChange,
  calculateVolatility,
  // 转换函数（供需要的地方使用）
  transformCandleToPricePoint,
  transformToPriceSeries,
  extractVolumePoints,
};

export default priceService;
