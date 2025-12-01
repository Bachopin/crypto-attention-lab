/**
 * 通用基础类型定义
 */

/**
 * 时间周期
 */
export type Timeframe = '1D' | '4H' | '1H' | '15M';

/**
 * 时间周期映射（前端格式 -> 后端格式）
 */
export const TIMEFRAME_MAP: Record<Timeframe, string> = {
  '1D': '1d',
  '4H': '4h',
  '1H': '1h',
  '15M': '15m',
};

/**
 * 后端时间周期格式
 */
export type BackendTimeframe = '1d' | '4h' | '1h' | '15m';

/**
 * 日期范围
 */
export interface DateRange {
  start?: string;
  end?: string;
}

/**
 * 分页参数
 */
export interface PaginationParams {
  page?: number;
  pageSize?: number;
  limit?: number;
  offset?: number;
}

/**
 * 排序参数
 */
export interface SortParams {
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

/**
 * 币种符号（不带 USDT 后缀）
 */
export type CryptoSymbol = string;

/**
 * 交易对符号（带 USDT 后缀）
 */
export type TradingPair = `${string}USDT`;

/**
 * 将币种符号转换为交易对
 */
export function toTradingPair(symbol: CryptoSymbol): TradingPair {
  if (symbol.endsWith('USDT')) {
    return symbol as TradingPair;
  }
  return `${symbol}USDT` as TradingPair;
}

/**
 * 从交易对提取币种符号
 */
export function fromTradingPair(pair: TradingPair): CryptoSymbol {
  return pair.replace('USDT', '');
}
