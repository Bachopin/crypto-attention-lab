/**
 * Core Data Models
 * 
 * These types represent the domain entities used throughout the application.
 */

export type Timeframe = '1D' | '4H' | '1H' | '15M';

export interface Candle {
  timestamp: number;     // Unix timestamp in milliseconds
  datetime: string;      // ISO 8601 format
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Alias for backward compatibility
export type PriceCandle = Candle;

export interface AttentionPoint {
  timestamp: number;
  datetime: string;
  attention_score: number;  // 0-100
  news_count: number;
  weighted_attention?: number;
  bullish_attention?: number;
  bearish_attention?: number;
  event_intensity?: number; // 0/1
  // Composite Attention fields
  news_channel_score?: number;
  google_trend_value?: number;
  google_trend_zscore?: number;
  twitter_volume?: number;
  twitter_volume_zscore?: number;
  composite_attention_score?: number;
  composite_attention_zscore?: number;
  composite_attention_spike_flag?: number;
}

export type AttentionData = AttentionPoint;

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

export interface AttentionEvent {
  datetime: string;
  event_type: 'attention_spike' | 'high_weighted_event' | 'high_bullish' | 'high_bearish' | 'event_intensity';
  intensity: number;
  summary: string;
}

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

export interface TopCoin {
  symbol: string;
  name: string;
  market_cap_rank: number | null;
  market_cap: number | null;
  current_price: number | null;
  price_change_24h: number | null;
  image: string;
  id: string;
}

// --- API Responses ---

export interface TopCoinsResponse {
  coins: TopCoin[];
  updated_at: string;
}

// --- Backtest Types ---

export interface EquityPoint {
  date?: string; // Optional because sometimes it's datetime
  datetime: string; // Required for charts
  equity: number;
  drawdown: number;
  price?: number;
  benchmark?: number;
}

export interface Trade {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  return_pct: number;
  holding_days: number;
  reason: string;
  symbol?: string; // For multi-symbol backtest
}

export interface AttentionCondition {
  operator?: 'gt' | 'lt' | 'gte' | 'lte';
  threshold?: number;
  metric?: 'attention_score' | 'composite_attention_score';
  
  // Fields used in presets and components
  source?: string;
  regime?: string;
  lower_quantile?: number;
  upper_quantile?: number;
  lookback_days?: number;
}

export interface BacktestSummary {
  total_return: number;
  cumulative_return: number; // Alias for total_return often used in UI
  annualized_return: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  sharpe_ratio: number;
  avg_return: number; // Average return per trade
  avg_trade_return?: number;
  attention_condition?: AttentionCondition;
  error?: string; // For error handling
}

export interface BacktestResult {
  params: any;
  meta?: {
    attention_source?: string;
    signal_field?: string;
    attention_condition?: AttentionCondition;
  };
  equity_curve: EquityPoint[];
  trades: Trade[];
  summary: BacktestSummary;
}

export interface MultiBacktestResult {
  params: any;
  meta?: {
    attention_source?: string;
  };
  aggregate_summary: BacktestSummary;
  aggregate_equity_curve: EquityPoint[];
  per_symbol_summary: Record<string, BacktestSummary>;
  per_symbol_trades: Record<string, Trade[]>;
  per_symbol_equity_curves?: Record<string, EquityPoint[]>;
  per_symbol_meta?: Record<string, any>;
}

export interface StrategyPreset {
  id: string;
  name: string;
  description: string;
  attention_condition?: AttentionCondition;
  params: {
    lookback_days: number;
    attention_quantile: number;
    holding_days: number;
    stop_loss_pct?: number;
    take_profit_pct?: number;
    attention_condition?: AttentionCondition;
  };
}

// --- Event Analysis Types ---

export interface EventPerformanceRow {
  event_type: string;
  count: number;
  avg_return_1d: number;
  avg_return_3d: number;
  avg_return_5d: number;
  avg_return_10d: number;
  win_rate_1d: number;
  win_rate_3d: number;
  win_rate_5d: number;
  win_rate_10d: number;
}

export interface EventPerformanceTable {
  symbol: string;
  updated_at: string;
  rows: EventPerformanceRow[];
  [key: string]: any; // Allow indexing by event type string
}

// --- Node Influence Types ---

export interface NodeInfluenceItem {
  node_id: string;
  symbol: string;
  influence_score: number;
  event_count: number;
  n_events?: number; // Alias
  mean_excess_return: number;
  hit_rate: number;
  ir: number; // Information Ratio
  lookahead?: number;
  lookback_days?: number;
}

// --- Research / Regime Types ---

export interface RegimeStats {
  count: number;
  avg_return: number;
  win_rate: number;
  volatility: number;
  sharpe: number;
}

export interface AttentionRegimeResponse {
  params: any;
  results: Record<string, any>; // Changed from regimes to results to match usage
  meta: {
    lookahead_days: number[];
    total_similar_samples?: number;
    valid_samples_analyzed?: number;
    message?: string;
  };
  data?: any; // Detailed data if needed
}

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

// --- Scenario Types ---

export type ScenarioSummary = {
  label: string;
  description: string;
  sample_count: number;
  probability: number;
  avg_return_3d?: number | null;
  avg_return_7d?: number | null;
  avg_return_30d?: number | null;
  max_drawdown_7d?: number | null;
  max_drawdown_30d?: number | null;
  avg_path?: number[] | null;
  sample_details?: any[] | null;
};

export type StateSnapshotSummary = {
  symbol: string;
  as_of: string;
  timeframe: string;
  window_days: number;
  features: Record<string, number>;
  raw_stats: Record<string, any>;
};

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
