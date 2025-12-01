/**
 * UI 状态类型定义
 * 
 * 用于统一管理异步数据获取的状态
 */

/**
 * 异步操作状态
 */
export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * 通用异步状态容器
 */
export interface AsyncState<T> {
  status: AsyncStatus;
  data: T | null;
  error: Error | null;
  /** 最后一次成功获取数据的时间戳 */
  lastUpdated: number | null;
}

/**
 * 创建初始异步状态
 */
export function createInitialAsyncState<T>(): AsyncState<T> {
  return {
    status: 'idle',
    data: null,
    error: null,
    lastUpdated: null,
  };
}

/**
 * 异步操作结果 - 用于 Hook 返回
 */
export interface AsyncResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  /** 是否正在后台刷新（有旧数据时的更新） */
  refreshing: boolean;
  /** 重新执行请求 */
  refresh: () => Promise<void>;
  /** 手动设置数据 */
  setData: (data: T | null) => void;
}

/**
 * 分页状态
 */
export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
  hasMore: boolean;
}

/**
 * 列表加载状态
 */
export interface ListState<T> extends AsyncState<T[]> {
  pagination: PaginationState | null;
  loadingMore: boolean;
}

/**
 * 表单字段状态
 */
export interface FieldState<T> {
  value: T;
  touched: boolean;
  error: string | null;
}

/**
 * WebSocket 连接状态
 */
export type WebSocketConnectionStatus = 
  | 'connecting' 
  | 'connected' 
  | 'disconnected' 
  | 'error' 
  | 'unavailable';

/**
 * 实时数据状态
 */
export interface RealtimeState<T> {
  data: T | null;
  status: WebSocketConnectionStatus;
  lastUpdate: Date | null;
  isRealtime: boolean;
}
