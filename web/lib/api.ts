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
  // Composite Attention fields (来自多渠道融合)
  news_channel_score?: number;
  google_trend_value?: number;
  google_trend_zscore?: number;
  twitter_volume?: number;
  twitter_volume_zscore?: number;
  composite_attention_score?: number;
  composite_attention_zscore?: number;
  composite_attention_spike_flag?: number;
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
  symbols?: string;
  language?: string;
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

// CoinGecko 市值排行数据
export interface TopCoin {
  symbol: string;
  name: string;
  market_cap_rank: number | null;
  market_cap: number | null;
  current_price: number | null;
  price_change_24h: number | null;
  image: string;
  id: string;  // CoinGecko ID
}

export interface TopCoinsResponse {
  coins: TopCoin[];
  count: number;
  updated_at: string;
  cache_hit: boolean;
  stale?: boolean;
  error?: string;
}

/**
 * ==========================================================================
 * Regime-Driven Strategy Preset Types
 * 用于研究注意力 Regime 驱动的策略，与后端 AttentionCondition 对齐
 * ==========================================================================
 */

/** 注意力条件，用于定义开仓日期的筛选逻辑 */
export type AttentionCondition = {
  source: 'composite' | 'news_channel';
  regime: 'low' | 'mid' | 'high' | 'custom';
  lower_quantile?: number | null;
  upper_quantile?: number | null;
  lookback_days: number;
};

/** 策略预设，包含一个可复用的 AttentionCondition 及元数据 */
export type StrategyPreset = {
  id: string;
  name: string;
  attention_condition: AttentionCondition;
  // 可预留扩展字段
};

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
  /** 若回测时提供了 attention_condition，将在此字段返回 */
  attention_condition?: AttentionCondition;
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
    attention_condition?: AttentionCondition;
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
  limit?: number;  // Maximum number of candles to return
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

const RAW_ENV_API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || '').trim();
const LOCAL_BACKEND_FALLBACK = 'http://localhost:8000';

function normalizeBaseUrl(base: string): string {
  if (!base) return '';
  return base.endsWith('/') ? base.slice(0, -1) : base;
}

export function getApiBaseUrl(): string {
  if (RAW_ENV_API_BASE_URL) {
    return normalizeBaseUrl(RAW_ENV_API_BASE_URL);
  }
  if (typeof window === 'undefined') {
    return LOCAL_BACKEND_FALLBACK;
  }
  return '';
}

export function buildApiUrl(path: string): string {
  const base = getApiBaseUrl();
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return base ? `${base}${normalizedPath}` : normalizedPath;
}

// Timeframe 映射: 前端格式 -> 后端格式
const TIMEFRAME_MAP: Record<Timeframe, string> = {
  '1D': '1d',
  '4H': '4h',
  '1H': '1h',
  '15M': '15m',
};

// ==================== Request Cache ====================

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

// 简单的内存缓存，TTL 30秒（适合实时数据）
const requestCache = new Map<string, CacheEntry<any>>();
const CACHE_TTL = 30 * 1000; // 30 seconds

function getCacheKey(endpoint: string, params: Record<string, any>): string {
  return `${endpoint}:${JSON.stringify(params)}`;
}

function getFromCache<T>(key: string): T | null {
  const entry = requestCache.get(key);
  if (entry && Date.now() - entry.timestamp < CACHE_TTL) {
    return entry.data as T;
  }
  // 清除过期缓存
  if (entry) {
    requestCache.delete(key);
  }
  return null;
}

function setToCache<T>(key: string, data: T): void {
  // 限制缓存大小，防止内存泄漏
  if (requestCache.size > 100) {
    const firstKey = requestCache.keys().next().value;
    if (firstKey) requestCache.delete(firstKey);
  }
  requestCache.set(key, { data, timestamp: Date.now() });
}

// 清除所有缓存（用于强制刷新）
export function clearApiCache(): void {
  requestCache.clear();
}

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

async function fetchAPI<T>(endpoint: string, params: Record<string, any> = {}, useCache = true): Promise<T> {
  const cacheKey = getCacheKey(endpoint, params);
  
  // 检查缓存
  if (useCache) {
    const cached = getFromCache<T>(cacheKey);
    if (cached !== null) {
      return cached;
    }
  }
  
  const url = `${buildApiUrl(endpoint)}${buildQueryString(params)}`;
  
  try {
    const response = await fetch(url);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    // 缓存成功的响应
    if (useCache) {
      setToCache(cacheKey, data);
    }
    
    return data;
  } catch (error) {
    console.error(`API request failed: ${url}`, error);
    throw error;
  }
}

// ==================== API Functions ====================

/**
 * Fetch price/OHLCV data from backend
 * GET /api/price?symbol=ZECUSDT&timeframe=1d&start=...&end=...
 * 
 * Note: If `limit` is provided without `start`, we calculate an approximate start date
 * based on the timeframe to fetch roughly that many candles.
 */
export async function fetchPrice(params: FetchPriceParams = {}): Promise<Candle[]> {
  const {
    symbol = 'ZECUSDT',
    timeframe = '1D',
    start,
    end,
    limit,
  } = params;

  // If limit is specified without start, calculate approximate start date
  let effectiveStart = start;
  if (limit && !start) {
    const now = new Date();
    const msPerCandle: Record<Timeframe, number> = {
      '1D': 24 * 60 * 60 * 1000,
      '4H': 4 * 60 * 60 * 1000,
      '1H': 60 * 60 * 1000,
      '15M': 15 * 60 * 1000,
    };
    const ms = msPerCandle[timeframe] * limit;
    const startDate = new Date(now.getTime() - ms);
    effectiveStart = startDate.toISOString();
  }

  const apiParams = {
    symbol,
    timeframe: TIMEFRAME_MAP[timeframe],
    start: effectiveStart,
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

// 新闻趋势数据点
export interface NewsTrendPoint {
  time: string;           // 时间标识，如 "2025-11-28" 或 "2025-11-28T14:00:00Z"
  count: number;          // 新闻数量
  /** @deprecated 请使用 attention_score，此字段仅保留向后兼容 */
  attention: number;      // [已弃用] 原始加权值（source_weight 总和）
  attention_score: number; // ⭐ 推荐使用：基于 Z-Score 的标准化分数 (0-100)
  z_score: number;        // 原始 Z-Score
  avg_sentiment: number;  // 平均情绪
}

/**
 * Fetch aggregated news trend data
 * GET /api/news/trend?symbol=ALL&start=...&end=...&interval=1d
 */
export async function fetchNewsTrend(params: { 
  symbol?: string; 
  start?: string; 
  end?: string; 
  interval?: '1h' | '1d';
} = {}): Promise<NewsTrendPoint[]> {
  const { symbol = 'ALL', start, end, interval = '1d' } = params;
  const apiParams = { symbol, start, end, interval };
  return fetchAPI<NewsTrendPoint[]>('/api/news/trend', apiParams);
}

/**
 * Fetch top coins by market cap from CoinGecko
 * GET /api/top-coins?limit=100
 */
export async function fetchTopCoins(limit: number = 100): Promise<TopCoinsResponse> {
  return fetchAPI<TopCoinsResponse>('/api/top-coins', { limit });
}

// ==================== New API: Events & Backtest ====================

export async function fetchAttentionEvents(params: { symbol?: string; start?: string; end?: string; lookback_days?: number; min_quantile?: number } = {}): Promise<AttentionEvent[]> {
  const { symbol = 'ZEC', start, end, lookback_days = 30, min_quantile = 0.8 } = params;
  const apiParams = { symbol, start, end, lookback_days, min_quantile };
  return fetchAPI<AttentionEvent[]>('/api/attention-events', apiParams);
}

export async function runBasicAttentionBacktest(params: { symbol?: string; lookback_days?: number; attention_quantile?: number; max_daily_return?: number; holding_days?: number; stop_loss_pct?: number | null; take_profit_pct?: number | null; max_holding_days?: number | null; position_size?: number; attention_source?: 'legacy' | 'composite'; attention_condition?: AttentionCondition | null; start?: string; end?: string } = {}): Promise<BacktestResult> {
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
    attention_condition: params.attention_condition ?? null,
    start: params.start,
    end: params.end,
  });
  const url = buildApiUrl('/api/backtest/basic-attention');
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
  attention_condition?: AttentionCondition | null;
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
    attention_condition: params.attention_condition ?? null,
    start: params.start,
    end: params.end,
  });
  const url = buildApiUrl('/api/backtest/basic-attention/multi');
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
  const url = buildApiUrl('/api/research/attention-regimes');
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

    const [priceData, latestPriceData, attentionData, newsData] = await Promise.all([
      fetchPrice({ symbol: `${symbol}USDT`, timeframe: '1D' }),
      fetchPrice({ symbol: `${symbol}USDT`, timeframe: '15M', start: yesterday.toISOString() }),
      fetchAttention({ symbol, start: weekAgo.toISOString() }),
      fetchNews({ symbol, start: yesterday.toISOString() }),
    ]);

    console.log('[Summary Stats] Price data points:', priceData.length);
    console.log('[Summary Stats] Latest price data points:', latestPriceData.length);
    console.log('[Summary Stats] Attention data points:', attentionData.length);
    console.log('[Summary Stats] News data points:', newsData.length);

    if (priceData.length === 0) {
      console.warn('[Summary Stats] No price data available');
      throw new Error('No price data available');
    }

    // Calculate stats
    // Use latest 15m candle for current price if available, otherwise fallback to daily close
    const latestCandle = latestPriceData.length > 0 ? latestPriceData[latestPriceData.length - 1] : priceData[priceData.length - 1];
    const current_price = latestCandle?.close || 0;
    
    // Use daily data for previous close (to calculate 24h change relative to daily open/close)
    // Note: priceData is 1D. The last element is "today" (incomplete). The second to last is "yesterday" (complete).
    // If we want change vs yesterday close:
    const previousPrice = priceData.length > 1 ? priceData[priceData.length - 2] : priceData[0];
    const prev_close = previousPrice?.close || current_price;
    
    const price_change_24h_abs = current_price - prev_close;
    const price_change_24h = prev_close !== 0 ? (price_change_24h_abs / prev_close) * 100 : 0;
    
    // For volume, use the daily volume (volume since 00:00 UTC)
    const volume_24h = priceData[priceData.length - 1]?.volume || 0;
    
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

// ==================== Scenario Engine Types ====================

/**
 * 情景摘要结构
 * 描述一种可能的未来走势情景
 */
export type ScenarioSummary = {
  label: string;                      // 情景标签: trend_up, spike_and_revert, sideways, trend_down, crash
  description: string;                // 人类可读描述
  sample_count: number;               // 样本数量
  probability: number;                // 相对概率 (0-1)
  avg_return_3d?: number | null;      // 3 日平均收益
  avg_return_7d?: number | null;      // 7 日平均收益
  avg_return_30d?: number | null;     // 30 日平均收益
  max_drawdown_7d?: number | null;    // 7 日平均最大回撤
  max_drawdown_30d?: number | null;   // 30 日平均最大回撤
  avg_path?: number[] | null;         // 平均价格路径（相对起点）
  sample_details?: any[] | null;      // 样本详情（可选）
};

/**
 * 状态快照摘要
 */
export type StateSnapshotSummary = {
  symbol: string;
  as_of: string;
  timeframe: string;
  window_days: number;
  features: Record<string, number>;
  raw_stats: Record<string, any>;
};

/**
 * 情景分析响应
 */
export type StateScenarioResponse = {
  target: StateSnapshotSummary;
  scenarios: ScenarioSummary[];
  meta: {
    total_similar_samples: number;
    valid_samples_analyzed: number;
    lookahead_days: number[];
    message: string;
  };
};

/**
 * 获取指定 symbol 的情景分析
 * GET /api/state/scenarios
 */
export async function fetchStateScenarios(params: {
  symbol: string;
  timeframe?: string;
  window_days?: number;
  top_k?: number;
  max_history_days?: number;
  include_sample_details?: boolean;
}): Promise<StateScenarioResponse> {
  const {
    symbol,
    timeframe = '1d',
    window_days = 30,
    top_k = 100,
    max_history_days = 365,
    include_sample_details = false,
  } = params;

  const apiParams = {
    symbol,
    timeframe,
    window_days,
    top_k,
    max_history_days,
    include_sample_details,
  };

  return fetchAPI<StateScenarioResponse>('/api/state/scenarios', apiParams);
}

/**
 * Attention Rotation Backtest Result
 */
export interface AttentionRotationResult {
  params: {
    symbols: string[];
    attention_source: string;
    rebalance_days: number;
    lookback_days: number;
    top_k: number;
    start?: string;
    end?: string;
  };
  equity_curve: EquityPoint[];
  rebalance_log: {
    rebalance_date: string;
    selected_symbols: string[];
    attention_values: Record<string, number>;
  }[];
  summary: {
    total_return: number;
    annualized_return: number;
    max_drawdown: number;
    volatility: number;
    sharpe: number;
    num_rebalances: number;
    start_date: string;
    end_date: string;
  };
}

export async function runAttentionRotationBacktest(params: {
  symbols: string[];
  attention_source?: 'composite' | 'news_channel';
  rebalance_days?: number;
  lookback_days?: number;
  top_k?: number;
  start?: string;
  end?: string;
}): Promise<AttentionRotationResult> {
  const body = JSON.stringify({
    symbols: params.symbols,
    attention_source: params.attention_source ?? 'composite',
    rebalance_days: params.rebalance_days ?? 7,
    lookback_days: params.lookback_days ?? 30,
    top_k: params.top_k ?? 3,
    start: params.start,
    end: params.end,
  });
  const url = buildApiUrl('/api/backtest/attention-rotation');
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
