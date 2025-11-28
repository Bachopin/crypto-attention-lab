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
  weighted_attention?: number;
  bullish_attention?: number;
  bearish_attention?: number;
  event_intensity?: number; // 0/1
}

export interface NewsItem {
  datetime: string;      // ISO 8601 format
  source: string;
  title: string;
  url: string;
  relevance?: string;
  source_weight?: number;
  sentiment_score?: number;
  tags?: string;
}

export interface NodeInfluenceItem {
  symbol: string;
  node_id: string;
  n_events: number;
  mean_excess_return: number;
  hit_rate: number;
  ir: number;
  lookahead: string;
  lookback_days: number;
}

// Events & Backtest Types
export interface AttentionEvent {
  datetime: string;
  event_type: 'attention_spike' | 'high_weighted_event' | 'high_bullish' | 'high_bearish' | 'event_intensity';
  intensity: number;
  summary: string;
}

export interface BacktestSummary {
  total_trades: number;
  win_rate: number; // percentage
  avg_return: number;
  cumulative_return: number;
  max_drawdown: number;
}

export interface BacktestTrade {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  return_pct: number;
}

export interface EquityPoint { datetime: string; equity: number }

export interface BacktestResult {
  summary: BacktestSummary;
  trades: BacktestTrade[];
  equity_curve: EquityPoint[];
  meta?: {
    attention_source?: 'legacy' | 'composite';
    signal_field?: string;
  };
}

export interface MultiBacktestResult {
  per_symbol_summary: Record<string, BacktestSummary | { error: string }>;
  per_symbol_equity_curves: Record<string, EquityPoint[]>;
  per_symbol_meta?: Record<string, { attention_source?: 'legacy' | 'composite'; signal_field?: string }>;
  meta?: {
    attention_source?: 'legacy' | 'composite';
    symbols?: string[];
  };
}

// Attention Regime Research Types
export interface AttentionRegimeLookaheadStats {
  avg_return: number | null;
  std_return: number | null;
  pos_ratio: number | null;
  max_drawdown: number | null;
  sample_count: number;
}

export interface AttentionRegimePerLabelStats {
  sample_count: number;
  [lookaheadKey: string]: any; // keys like "lookahead_7d" map to AttentionRegimeLookaheadStats
}

export interface AttentionRegimeSymbolResult {
  attention_source: string;
  attention_column: string;
  split_method: string;
  labels: string[];
  regimes: Record<string, AttentionRegimePerLabelStats>;
  warning?: string;
}

export interface AttentionRegimeResponse {
  meta: {
    symbols: string[];
    lookahead_days: number[];
    start?: string | null;
    end?: string | null;
  };
  results: Record<string, AttentionRegimeSymbolResult>;
}

export type EventPerformanceTable = Record<string, Record<string, {
  event_type: string;
  lookahead_days: number;
  avg_return: number;
  sample_size: number;
}>>

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

export type Timeframe = '1D' | '4H' | '1H' | '15M';

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
  limit?: number;
  before?: string;
  source?: string;
}

// ==================== API Configuration ====================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Timeframe 映射: 前端格式 -> 后端格式
const TIMEFRAME_MAP: Record<Timeframe, string> = {
  '1D': '1d',
  '4H': '4h',
  '1H': '1h',
  '15M': '15m',
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
 * GET /api/news?symbol=ALL&start=...&end=...
 */
export async function fetchNews(params: FetchNewsParams = {}): Promise<NewsItem[]> {
  const {
    symbol = 'ALL',
    start,
    end,
    limit,
    before,
    source,
  } = params;

  const apiParams = {
    symbol,
    start,
    end,
    limit,
    before,
    source,
  };
  return fetchAPI<NewsItem[]>('/api/news', apiParams);
}

export async function fetchNewsCount(params: FetchNewsParams = {}): Promise<{ total: number }> {
  const { symbol = 'ALL', start, end, before, source } = params;
  const apiParams = { symbol, start, end, before, source };
  return fetchAPI<{ total: number }>('/api/news/count', apiParams);
}

// ==================== New API: Events & Backtest ====================

export async function fetchAttentionEvents(params: { symbol?: string; start?: string; end?: string; lookback_days?: number; min_quantile?: number } = {}): Promise<AttentionEvent[]> {
  const { symbol = 'ZEC', start, end, lookback_days = 30, min_quantile = 0.8 } = params;
  const apiParams = { symbol, start, end, lookback_days, min_quantile };
  return fetchAPI<AttentionEvent[]>('/api/attention-events', apiParams);
}

export async function runBasicAttentionBacktest(params: { symbol?: string; lookback_days?: number; attention_quantile?: number; max_daily_return?: number; holding_days?: number; stop_loss_pct?: number | null; take_profit_pct?: number | null; max_holding_days?: number | null; position_size?: number; attention_source?: 'legacy' | 'composite'; start?: string; end?: string } = {}): Promise<BacktestResult> {
  const body = JSON.stringify({
    symbol: params.symbol ?? 'ZECUSDT',
    lookback_days: params.lookback_days ?? 30,
    attention_quantile: params.attention_quantile ?? 0.8,
    max_daily_return: params.max_daily_return ?? 0.05,
    holding_days: params.holding_days ?? 3,
    stop_loss_pct: params.stop_loss_pct,
    take_profit_pct: params.take_profit_pct,
    max_holding_days: params.max_holding_days,
    position_size: params.position_size,
    attention_source: params.attention_source,
    start: params.start,
    end: params.end,
  });
  const url = `${API_BASE_URL}/api/backtest/basic-attention`;
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function runMultiSymbolBacktest(params: {
  symbols: string[];
  lookback_days?: number;
  attention_quantile?: number;
  max_daily_return?: number;
  holding_days?: number;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
  max_holding_days?: number | null;
  position_size?: number;
  attention_source?: 'legacy' | 'composite';
  start?: string;
  end?: string;
}): Promise<MultiBacktestResult> {
  const body = JSON.stringify({
    symbols: params.symbols,
    lookback_days: params.lookback_days ?? 30,
    attention_quantile: params.attention_quantile ?? 0.8,
    max_daily_return: params.max_daily_return ?? 0.05,
    holding_days: params.holding_days ?? 3,
    stop_loss_pct: params.stop_loss_pct,
    take_profit_pct: params.take_profit_pct,
    max_holding_days: params.max_holding_days,
    position_size: params.position_size ?? 1.0,
    attention_source: params.attention_source,
    start: params.start,
    end: params.end,
  });
  const url = `${API_BASE_URL}/api/backtest/basic-attention/multi`;
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchAttentionEventPerformance(params: { symbol?: string; lookahead_days?: string } = {}): Promise<EventPerformanceTable> {
  const { symbol = 'ZEC', lookahead_days = '1,3,5,10' } = params
  return fetchAPI<EventPerformanceTable>('/api/attention-events/performance', { symbol, lookahead_days })
}

/**
 * Fetch node influence (carry factor) list
 * GET /api/node-influence?symbol=ZEC&min_events=10&sort_by=ir&limit=100
 */
export async function fetchNodeInfluence(params: { symbol?: string; min_events?: number; sort_by?: 'ir' | 'mean_excess_return' | 'hit_rate'; limit?: number } = {}): Promise<NodeInfluenceItem[]> {
  const { symbol, min_events = 10, sort_by = 'ir', limit = 100 } = params;
  const apiParams: Record<string, any> = { min_events, sort_by, limit };
  if (symbol) apiParams.symbol = symbol;
  return fetchAPI<NodeInfluenceItem[]>('/api/node-influence', apiParams);
}

// ==================== Research: Attention Regimes ====================
export async function fetchAttentionRegimeAnalysis(params: {
  symbols: string[];
  lookahead_days?: number[];
  attention_source?: 'composite' | 'news_channel' | 'google_channel' | 'twitter_channel';
  split_method?: 'tercile' | 'quartile';
  split_quantiles?: number[];
  start?: string;
  end?: string;
}): Promise<AttentionRegimeResponse> {
  const body = JSON.stringify({
    symbols: params.symbols,
    lookahead_days: params.lookahead_days ?? [7, 30],
    attention_source: params.attention_source ?? 'composite',
    split_method: params.split_method ?? 'tercile',
    split_quantiles: params.split_quantiles,
    start: params.start,
    end: params.end,
  });
  const url = `${API_BASE_URL}/api/research/attention-regimes`;
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
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
