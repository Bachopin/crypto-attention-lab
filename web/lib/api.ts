// ==================== Type Definitions ====================

// 与后端 API 完全对应的类型定义

export interface Candle {
  timestamp: number;     // Unix timestamp in milliseconds
  datetime: string;      // ISO 8601 format
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface AttentionPoint {
  timestamp: number;
  datetime: string;
  attention_score: number;  // 0-100
  news_count: number;
}

export interface NewsItem {
  datetime: string;      // ISO 8601 format
  source: string;
  title: string;
  url: string;
}

// 兼容旧代码的类型别名
export type PriceCandle = Candle;
export type AttentionData = AttentionPoint;

export interface SummaryStats {
  current_price: number;
  price_change_24h: number; // percentage
  price_change_24h_abs: number; // absolute value
  volume_24h: number;
  current_attention: number;
  avg_attention_7d: number;
  news_count_today: number;
  volatility_30d: number; // percentage
}

export type Timeframe = '1D' | '4H' | '1H' | '15M' | '5M' | '1M';

export interface FetchPriceParams {
  symbol?: string;
  timeframe?: Timeframe;
  start?: string;  // ISO 8601 format
  end?: string;    // ISO 8601 format
}

export interface FetchAttentionParams {
  symbol?: string;
  granularity?: '1d';
  start?: string;
  end?: string;
}

export interface FetchNewsParams {
  symbol?: string;
  start?: string;
  end?: string;
}

// ==================== API Configuration ====================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Timeframe 映射: 前端格式 -> 后端格式
const TIMEFRAME_MAP: Record<Timeframe, string> = {
  '1D': '1d',
  '4H': '4h',
  '1H': '1h',
  '15M': '15m',
  '5M': '5m',
  '1M': '1m',
};

// ==================== Helper Functions ====================

function buildQueryString(params: Record<string, any>): string {
  const query = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      query.append(key, String(value));
    }
  });
  
  const queryString = query.toString();
  return queryString ? `?${queryString}` : '';
}

async function fetchAPI<T>(endpoint: string, params: Record<string, any> = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}${buildQueryString(params)}`;
  
  try {
    const response = await fetch(url);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`API request failed: ${url}`, error);
    throw error;
  }
}

// ==================== API Functions ====================

/**
 * Fetch price/OHLCV data from backend
 * GET /api/price?symbol=ZECUSDT&timeframe=1d&start=...&end=...
 */
export async function fetchPrice(params: FetchPriceParams = {}): Promise<Candle[]> {
  const {
    symbol = 'ZECUSDT',
    timeframe = '1D',
    start,
    end,
  } = params;

  const apiParams = {
    symbol,
    timeframe: TIMEFRAME_MAP[timeframe],
    start,
    end,
  };

  return fetchAPI<Candle[]>('/api/price', apiParams);
}

/**
 * Fetch attention score data from backend
 * GET /api/attention?symbol=ZEC&granularity=1d&start=...&end=...
 */
export async function fetchAttention(params: FetchAttentionParams = {}): Promise<AttentionPoint[]> {
  const {
    symbol = 'ZEC',
    granularity = '1d',
    start,
    end,
  } = params;

  const apiParams = {
    symbol,
    granularity,
    start,
    end,
  };

  return fetchAPI<AttentionPoint[]>('/api/attention', apiParams);
}

/**
 * Fetch news items from backend
 * GET /api/news?symbol=ZEC&start=...&end=...
 */
export async function fetchNews(params: FetchNewsParams = {}): Promise<NewsItem[]> {
  const {
    symbol = 'ZEC',
    start,
    end,
  } = params;

  const apiParams = {
    symbol,
    start,
    end,
  };

  return fetchAPI<NewsItem[]>('/api/news', apiParams);
}

/**
 * Calculate summary statistics from price and attention data
 * Note: This is computed client-side since backend doesn't have a summary endpoint yet
 */
export async function fetchSummaryStats(symbol: string = 'ZEC'): Promise<SummaryStats> {
  try {
    // Fetch recent data
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

    const [priceData, attentionData, newsData] = await Promise.all([
      fetchPrice({ symbol: `${symbol}USDT`, timeframe: '1D' }),
      fetchAttention({ symbol, start: weekAgo.toISOString() }),
      fetchNews({ symbol, start: yesterday.toISOString() }),
    ]);

    console.log('[Summary Stats] Price data points:', priceData.length);
    console.log('[Summary Stats] Attention data points:', attentionData.length);
    console.log('[Summary Stats] News data points:', newsData.length);

    if (priceData.length === 0) {
      console.warn('[Summary Stats] No price data available');
      throw new Error('No price data available');
    }

    // Calculate stats
    const latestPrice = priceData[priceData.length - 1];
    const previousPrice = priceData[priceData.length - 2];
    
    const current_price = latestPrice?.close || 0;
    const prev_close = previousPrice?.close || current_price;
    const price_change_24h_abs = current_price - prev_close;
    const price_change_24h = prev_close !== 0 ? (price_change_24h_abs / prev_close) * 100 : 0;
    
    const volume_24h = latestPrice?.volume || 0;
    
    const current_attention = attentionData[attentionData.length - 1]?.attention_score || 0;
    const avg_attention_7d = attentionData.length > 0
      ? attentionData.reduce((sum, d) => sum + d.attention_score, 0) / attentionData.length
      : 0;
    
    const news_count_today = newsData.length;
    
    // Calculate 30-day volatility
    const monthData = priceData.slice(-30);
    const returns = monthData.slice(1).map((d, i) => {
      const prevClose = monthData[i].close;
      return prevClose !== 0 ? (d.close - prevClose) / prevClose : 0;
    });
    const volatility_30d = returns.length > 0
      ? Math.sqrt(returns.reduce((sum, r) => sum + r * r, 0) / returns.length) * 100
      : 0;

    const stats = {
      current_price,
      price_change_24h,
      price_change_24h_abs,
      volume_24h,
      current_attention,
      avg_attention_7d,
      news_count_today,
      volatility_30d,
    };

    console.log('[Summary Stats] Calculated:', stats);
    return stats;
  } catch (error) {
    console.error('Failed to calculate summary stats:', error);
    // Return default values on error
    return {
      current_price: 0,
      price_change_24h: 0,
      price_change_24h_abs: 0,
      volume_24h: 0,
      current_attention: 0,
      avg_attention_7d: 0,
      news_count_today: 0,
      volatility_30d: 0,
    };
  }
}
