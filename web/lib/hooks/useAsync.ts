/**
 * useAsync - 通用异步数据获取 Hook
 * 
 * 提供统一的加载、错误、刷新状态管理
 * 不引入外部依赖，基于 React 内置 hooks 实现
 * 
 * @example
 * ```tsx
 * const { data, loading, error, refresh } = useAsync(
 *   () => priceService.getPriceData('BTC', '1D'),
 *   [symbol, timeframe]
 * );
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { AsyncResult } from '@/types/ui';

/**
 * useAsync 配置选项
 */
export interface UseAsyncOptions {
  /** 是否立即执行（默认 true） */
  immediate?: boolean;
  /** 是否启用（默认 true，设为 false 时不执行） */
  enabled?: boolean;
  /** 依赖变化时是否保留旧数据（默认 false） */
  keepPreviousData?: boolean;
  /** 错误时的重试次数（默认 0） */
  retryCount?: number;
  /** 重试延迟（毫秒，默认 1000） */
  retryDelay?: number;
  /** 数据过期时间（毫秒，默认无限） */
  staleTime?: number;
  /** 成功回调 */
  onSuccess?: (data: any) => void;
  /** 错误回调 */
  onError?: (error: Error) => void;
}

/**
 * 通用异步数据获取 Hook
 * 
 * @param asyncFn 异步函数
 * @param deps 依赖数组，变化时重新执行
 * @param options 配置选项
 * @returns AsyncResult
 */
export function useAsync<T>(
  asyncFn: () => Promise<T>,
  deps: React.DependencyList = [],
  options: UseAsyncOptions = {}
): AsyncResult<T> {
  const {
    immediate = true,
    enabled = true,
    keepPreviousData = false,
    retryCount = 0,
    retryDelay = 1000,
    staleTime,
    onSuccess,
    onError,
  } = options;

  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(immediate);
  const [refreshing, setRefreshing] = useState(false);

  // 用于追踪最新请求，避免竞态条件
  const requestIdRef = useRef(0);
  // 用于追踪数据获取时间（用于 staleTime）
  const lastFetchTimeRef = useRef<number | null>(null);
  // 用于追踪重试次数
  const retryCountRef = useRef(0);

  const execute = useCallback(async (isRefresh = false) => {
    const currentRequestId = ++requestIdRef.current;

    // 检查数据是否过期
    if (
      staleTime &&
      lastFetchTimeRef.current &&
      Date.now() - lastFetchTimeRef.current < staleTime &&
      data !== null
    ) {
      return;
    }

    if (isRefresh && data !== null) {
      setRefreshing(true);
    } else {
      if (!keepPreviousData) {
        setData(null);
      }
      setLoading(true);
    }
    setError(null);

    try {
      const result = await asyncFn();

      // 检查是否是最新请求
      if (currentRequestId !== requestIdRef.current) {
        return;
      }

      setData(result);
      lastFetchTimeRef.current = Date.now();
      retryCountRef.current = 0;
      onSuccess?.(result);
    } catch (err) {
      // 检查是否是最新请求
      if (currentRequestId !== requestIdRef.current) {
        return;
      }

      const error = err instanceof Error ? err : new Error(String(err));

      // 重试逻辑
      if (retryCountRef.current < retryCount) {
        retryCountRef.current++;
        setTimeout(() => {
          execute(isRefresh);
        }, retryDelay);
        return;
      }

      setError(error);
      onError?.(error);
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [asyncFn, data, keepPreviousData, retryCount, retryDelay, staleTime, onSuccess, onError]);

  const refresh = useCallback(async () => {
    await execute(true);
  }, [execute]);

  // 依赖变化时重新执行
  useEffect(() => {
    if (immediate && enabled) {
      execute(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled]);

  return {
    data,
    loading,
    error,
    refreshing,
    refresh,
    setData,
  };
}

/**
 * useAsyncCallback - 手动触发的异步操作 Hook
 * 
 * 适用于用户交互触发的操作（如提交表单、触发回测）
 * 
 * @example
 * ```tsx
 * const { execute, loading, error } = useAsyncCallback(
 *   (params) => backtestService.runBacktest(params)
 * );
 * 
 * <button onClick={() => execute(formData)} disabled={loading}>
 *   Run Backtest
 * </button>
 * ```
 */
export function useAsyncCallback<T, Args extends any[]>(
  asyncFn: (...args: Args) => Promise<T>,
  options: Omit<UseAsyncOptions, 'immediate'> = {}
): {
  execute: (...args: Args) => Promise<T | null>;
  data: T | null;
  loading: boolean;
  error: Error | null;
  reset: () => void;
} {
  const { onSuccess, onError, retryCount = 0, retryDelay = 1000 } = options;

  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);

  const retryCountRef = useRef(0);

  const execute = useCallback(async (...args: Args): Promise<T | null> => {
    setLoading(true);
    setError(null);

    try {
      const result = await asyncFn(...args);
      setData(result);
      retryCountRef.current = 0;
      onSuccess?.(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));

      // 重试逻辑
      if (retryCountRef.current < retryCount) {
        retryCountRef.current++;
        await new Promise(resolve => setTimeout(resolve, retryDelay));
        return execute(...args);
      }

      setError(error);
      onError?.(error);
      return null;
    } finally {
      setLoading(false);
    }
  }, [asyncFn, onSuccess, onError, retryCount, retryDelay]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
    retryCountRef.current = 0;
  }, []);

  return { execute, data, loading, error, reset };
}

/**
 * useDebouncedAsync - 带防抖的异步 Hook
 * 
 * 适用于搜索等频繁触发的场景
 */
export function useDebouncedAsync<T>(
  asyncFn: () => Promise<T>,
  deps: React.DependencyList = [],
  delay: number = 300,
  options: UseAsyncOptions = {}
): AsyncResult<T> {
  const [debouncedDeps, setDebouncedDeps] = useState(deps);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      setDebouncedDeps(deps);
    }, delay);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return useAsync(asyncFn, debouncedDeps, options);
}

export default useAsync;
