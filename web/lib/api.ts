// ==================== Type Definitions ====================

// Re-export core models from the new types directory
export * from '@/types/models';

import { 
  Candle, 
  AttentionPoint, 
  NewsItem, 
  AttentionEvent, 
  SummaryStats, 
  Timeframe, 
  TopCoinsResponse,
  TopCoin,
  BacktestResult,
  MultiBacktestResult,
  EventPerformanceTable,
  NodeInfluenceItem,
  AttentionRegimeResponse,
  AttentionRotationResult,
  StateScenarioResponse,
  AttentionCondition,
  NewsTrendPoint,
  ScenarioSummary,
  StateSnapshotSummary,
  EquityPoint
} from '@/types/models';

// ==================== API Configuration ====================

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

export async function fetchSymbols(): Promise<{ symbols: string[] }> {
  return fetchAPI<{ symbols: string[] }>('/api/symbols');
}

// ==================== API Configuration ====================

const RAW_ENV_API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || '').trim();
const LOCAL_BACKEND_FALLBACK = 'http://127.0.0.1:8000';

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

// 简单的内存缓存，TTL 5分钟（价格数据变化不频繁，延长缓存减少请求）
const requestCache = new Map<string, CacheEntry<any>>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
const MAX_CACHE_SIZE = 50; // 限制缓存条数，防止无限增长

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

function cleanExpiredCache(): void {
  const now = Date.now();
  const keysToDelete: string[] = [];
  
  for (const [key, entry] of requestCache.entries()) {
    if (now - entry.timestamp > CACHE_TTL) {
      keysToDelete.push(key);
    }
  }
  
  keysToDelete.forEach(key => requestCache.delete(key));
}

function setToCache<T>(key: string, data: T): void {
  // 主动清理过期缓存
  cleanExpiredCache();
  
  // 如果仍然超过限制，删除最旧的条目（LRU策略）
  if (requestCache.size >= MAX_CACHE_SIZE) {
    let oldestKey: string | null = null;
    let oldestTime = Date.now();
    
    for (const [k, entry] of requestCache.entries()) {
      if (entry.timestamp < oldestTime) {
        oldestTime = entry.timestamp;
        oldestKey = k;
      }
    }
    
    if (oldestKey) {
      requestCache.delete(oldestKey);
    }
  }
  
  requestCache.set(key, { data, timestamp: Date.now() });
}

// 清除所有缓存（用于强制刷新）
export function clearApiCache(): void {
  requestCache.clear();
}

// 获取缓存大小（用于调试）
export function getCacheSize(): number {
  return requestCache.size;
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

// ==================== Error Handling ====================

export class ApiError extends Error {
  constructor(
    public message: string,
    public statusCode?: number,
    public endpoint?: string,
    public details?: any
  ) {
    super(message);
    this.name = 'ApiError';
  }
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
      let errorDetails;
      try {
        errorDetails = await response.json();
      } catch (e) {
        errorDetails = { detail: response.statusText };
      }

      const message = errorDetails.detail || `Request failed with status ${response.status}`;
      console.error(`[API Error] ${endpoint}:`, { status: response.status, detail: message, errorDetails });
      throw new ApiError(message, response.status, endpoint, errorDetails);
    }
    
    const data = await response.json();
    
    // 简单的结构检查：如果期望是数组但拿到 null/undefined，抛出错误
    // 注意：这里无法在运行时完全验证泛型 T，只能做基础防卫
    if (data === null || data === undefined) {
       throw new ApiError('API returned empty response', response.status, endpoint);
    }

    // 缓存成功的响应
    if (useCache) {
      setToCache(cacheKey, data);
    }
    
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    // 网络错误或其他 fetch 异常
    console.error(`API request failed: ${url}`, error);
    throw new ApiError(error instanceof Error ? error.message : 'Network error', 0, endpoint);
  }
}

async function postAPI<T>(endpoint: string, body: any): Promise<T> {
  const url = buildApiUrl(endpoint);
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      let errorDetails;
      try {
        errorDetails = await response.json();
      } catch (e) {
        errorDetails = { detail: response.statusText };
      }
      const message = errorDetails.detail || `Request failed with status ${response.status}`;
      throw new ApiError(message, response.status, endpoint, errorDetails);
    }

    const data = await response.json();
    if (data === null || data === undefined) {
       throw new ApiError('API returned empty response', response.status, endpoint);
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    console.error(`API request failed: ${url}`, error);
    throw new ApiError(error instanceof Error ? error.message : 'Network error', 0, endpoint);
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

  // 禁用缓存：时间范围参数经常变化
  return fetchAPI<Candle[]>('/api/price', apiParams, false);
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

  // 禁用缓存：时间范围参数经常变化
  return fetchAPI<AttentionPoint[]>('/api/attention', apiParams, false);
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
  // 禁用缓存：时间范围和其他参数经常变化
  return fetchAPI<NewsItem[]>('/api/news', apiParams, false);
}

export async function fetchNewsCount(params: FetchNewsParams = {}): Promise<{ total: number }> {
  const { symbol = 'ALL', start, end, before, source } = params;
  const apiParams = { symbol, start, end, before, source };
  // 禁用缓存：时间范围参数经常变化
  return fetchAPI<{ total: number }>('/api/news/count', apiParams, false);
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
  // 禁用缓存：时间范围和间隔参数经常变化
  return fetchAPI<NewsTrendPoint[]>('/api/news/trend', apiParams, false);
}

/**
 * Fetch top coins by market cap from CoinGecko
 * GET /api/top-coins?limit=100
 */
export async function fetchTopCoins(limit: number = 100): Promise<TopCoinsResponse> {
  try {
    return await fetchAPI<TopCoinsResponse>('/api/top-coins', { limit });
  } catch (error) {
    console.warn('[fetchTopCoins] CoinGecko unavailable, returning fallback:', error);
    // 前端降级：返回硬编码常见 top coins
    return {
      coins: [
        { symbol: 'BTC', name: 'Bitcoin', market_cap_rank: 1, market_cap: null, current_price: null, price_change_24h: null, image: '', id: 'bitcoin' },
        { symbol: 'ETH', name: 'Ethereum', market_cap_rank: 2, market_cap: null, current_price: null, price_change_24h: null, image: '', id: 'ethereum' },
        { symbol: 'BNB', name: 'BNB', market_cap_rank: 4, market_cap: null, current_price: null, price_change_24h: null, image: '', id: 'binancecoin' },
        { symbol: 'SOL', name: 'Solana', market_cap_rank: 5, market_cap: null, current_price: null, price_change_24h: null, image: '', id: 'solana' },
      ],
      count: 4,
      updated_at: new Date().toISOString(),
      fallback: true,
    };
  }
}

// ==================== New API: Events & Backtest ====================

export async function fetchAttentionEvents(params: { symbol?: string; start?: string; end?: string; lookback_days?: number; min_quantile?: number } = {}): Promise<AttentionEvent[]> {
  const { symbol = 'ZEC', start, end, lookback_days = 30, min_quantile = 0.8 } = params;
  const apiParams = { symbol, start, end, lookback_days, min_quantile };
  // 禁用缓存，因为此端点经常用于特定时间范围查询，缓存会导致不准确的结果
  return fetchAPI<AttentionEvent[]>('/api/attention-events', apiParams, false);
}

export async function runBasicAttentionBacktest(params: { symbol?: string; lookback_days?: number; attention_quantile?: number; max_daily_return?: number; holding_days?: number; stop_loss_pct?: number | null; take_profit_pct?: number | null; max_holding_days?: number | null; position_size?: number; attention_source?: 'legacy' | 'composite'; attention_condition?: AttentionCondition | null; start?: string; end?: string } = {}): Promise<BacktestResult> {
  const body = {
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
  };
  return postAPI<BacktestResult>('/api/backtest/basic-attention', body);
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
  const body = {
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
  };
  return postAPI<MultiBacktestResult>('/api/backtest/basic-attention/multi', body);
}

export async function fetchAttentionEventPerformance(params: { symbol?: string; lookahead_days?: string } = {}): Promise<EventPerformanceTable> {
  const { symbol = 'ZEC', lookahead_days = '1,3,5,10' } = params
  // 禁用缓存：symbol 参数变化时需要新的性能数据
  return fetchAPI<EventPerformanceTable>('/api/attention-events/performance', { symbol, lookahead_days }, false)
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
  const body = {
    symbols: params.symbols,
    lookahead_days: params.lookahead_days ?? [7, 30],
    attention_source: params.attention_source ?? 'composite',
    split_method: params.split_method ?? 'tercile',
    split_quantiles: params.split_quantiles,
    start: params.start,
    end: params.end,
  };
  return postAPI<AttentionRegimeResponse>('/api/research/attention-regimes', body);
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

    // 数据已加载，计算统计信息

    if (priceData.length === 0) {
      // 没有价格数据
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
    
    // Calculate Attention Score (0-100)
    // Priority: 
    // 1. composite_attention_score (converted from z-score to 0-100) -> captures News + Social + Search
    // 2. attention_score (based on news count) -> fallback
    const latestAtt = attentionData[attentionData.length - 1];
    let current_attention = 0;
    
    if (latestAtt) {
      if (latestAtt.composite_attention_score !== undefined) {
        // Convert Z-score like value to 0-100 scale (mean 50, std ~15)
        current_attention = Math.max(0, Math.min(100, 50 + (latestAtt.composite_attention_score * 15)));
      } else {
        current_attention = latestAtt.attention_score ?? 0;
      }
    }

    // Calculate 7d Average
    const avg_attention_7d = attentionData.length > 0
      ? attentionData.reduce((sum, d) => {
          let val = 0;
          if (d.composite_attention_score !== undefined) {
             val = Math.max(0, Math.min(100, 50 + (d.composite_attention_score * 15)));
          } else {
             val = d.attention_score ?? 0;
          }
          return sum + val;
        }, 0) / attentionData.length
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

    // 统计信息计算完成
    return stats;
  } catch (error) {
    // 计算失败，返回默认值
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
    timeframe: timeframe.toLowerCase(),
    window_days,
    top_k,
    max_history_days,
    include_sample_details,
  };

  return fetchAPI<StateScenarioResponse>('/api/state/scenarios', apiParams);
}

/**
 * 获取单个情景详情
 * GET /api/state/scenario/:id
 * TODO: 需要后端实现
 */
export async function fetchScenarioDetail(scenarioId: string): Promise<unknown> {
  return fetchAPI<unknown>(`/api/state/scenario/${scenarioId}`);
}

/**
 * 根据事件获取情景分析
 * GET /api/state/event-scenario
 * TODO: 需要后端实现
 */
export async function fetchEventScenario(params: {
  symbol: string;
  event_type: string;
  event_date?: string;
}): Promise<unknown> {
  return fetchAPI<unknown>('/api/state/event-scenario', params);
}

/**
 * 获取当前状态快照
 * GET /api/state/snapshot
 * TODO: 需要后端实现
 */
export async function fetchStateSnapshot(symbol: string): Promise<unknown> {
  return fetchAPI<unknown>('/api/state/snapshot', { symbol });
}

/**
 * 搜索相似历史状态
 * GET /api/state/similar
 * TODO: 需要后端实现
 */
export async function fetchSimilarStates(params: {
  symbol: string;
  timeframe?: string;
  lookback_days?: number;
  top_n?: number;
  weight_attention?: number;
  weight_price?: number;
  weight_volume?: number;
  weight_regime?: number;
}): Promise<unknown[]> {
  return fetchAPI<unknown[]>('/api/state/similar', params);
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
  const body = {
    symbols: params.symbols,
    attention_source: params.attention_source ?? 'composite',
    rebalance_days: params.rebalance_days ?? 7,
    lookback_days: params.lookback_days ?? 30,
    top_k: params.top_k ?? 3,
    start: params.start,
    end: params.end,
  };
  return postAPI<AttentionRotationResult>('/api/backtest/attention-rotation', body);
}
