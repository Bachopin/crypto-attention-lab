'use client';

/**
 * AsyncBoundary - 统一的异步状态边界组件
 * 
 * 提供一致的加载、错误、空状态 UI 处理
 * 
 * @example
 * ```tsx
 * <AsyncBoundary loading={loading} error={error} data={data}>
 *   <MyComponent data={data} />
 * </AsyncBoundary>
 * ```
 */

import React from 'react';
import { AlertTriangle, RefreshCw, Inbox, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

// ==================== Loading States ====================

export interface LoadingSkeletonProps {
  /** 高度 */
  height?: number | string;
  /** 类名 */
  className?: string;
  /** 变体 */
  variant?: 'card' | 'chart' | 'list' | 'table' | 'inline';
}

/**
 * 加载骨架屏
 */
export function LoadingSkeleton({ 
  height = 200, 
  className = '',
  variant = 'card'
}: LoadingSkeletonProps) {
  const heightStyle = typeof height === 'number' ? `${height}px` : height;

  switch (variant) {
    case 'chart':
      return (
        <div 
          className={`bg-muted/50 rounded-lg animate-pulse flex items-center justify-center ${className}`}
          style={{ height: heightStyle }}
        >
          <div className="flex flex-col items-center gap-2 text-muted-foreground">
            <Loader2 className="w-6 h-6 animate-spin" />
            <span className="text-sm">Loading chart...</span>
          </div>
        </div>
      );

    case 'list':
      return (
        <div className={`space-y-3 ${className}`}>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center gap-3 animate-pulse">
              <div className="w-10 h-10 bg-muted rounded-full" />
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-muted rounded w-3/4" />
                <div className="h-3 bg-muted rounded w-1/2" />
              </div>
            </div>
          ))}
        </div>
      );

    case 'table':
      return (
        <div className={`space-y-2 ${className}`}>
          <div className="h-10 bg-muted rounded animate-pulse" />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-12 bg-muted/50 rounded animate-pulse" />
          ))}
        </div>
      );

    case 'inline':
      return (
        <span className="inline-flex items-center gap-2 text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Loading...</span>
        </span>
      );

    case 'card':
    default:
      return (
        <div 
          className={`bg-muted/50 rounded-lg animate-pulse ${className}`}
          style={{ height: heightStyle }}
        />
      );
  }
}

/**
 * 居中加载 Spinner
 */
export function LoadingSpinner({ 
  message = 'Loading...',
  size = 'md'
}: { 
  message?: string;
  size?: 'sm' | 'md' | 'lg';
}) {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <Loader2 className={`${sizeClasses[size]} animate-spin text-primary`} />
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
    </div>
  );
}

// ==================== Error States ====================

export interface ErrorStateProps {
  /** 错误信息 */
  message?: string;
  /** 详细错误（开发环境显示） */
  details?: string;
  /** 重试回调 */
  onRetry?: () => void;
  /** 是否紧凑模式 */
  compact?: boolean;
  /** 变体 */
  variant?: 'default' | 'inline' | 'card';
}

/**
 * 错误状态组件
 */
export function ErrorState({
  message = 'An error occurred',
  details,
  onRetry,
  compact = false,
  variant = 'default'
}: ErrorStateProps) {
  if (variant === 'inline') {
    return (
      <span className="inline-flex items-center gap-2 text-destructive text-sm">
        <AlertTriangle className="w-4 h-4" />
        <span>{message}</span>
        {onRetry && (
          <button 
            onClick={onRetry}
            className="underline hover:no-underline"
          >
            Retry
          </button>
        )}
      </span>
    );
  }

  if (variant === 'card') {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-destructive mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-destructive">{message}</p>
            {details && process.env.NODE_ENV === 'development' && (
              <pre className="mt-2 text-xs text-muted-foreground overflow-auto max-h-24">
                {details}
              </pre>
            )}
            {onRetry && (
              <Button 
                variant="outline" 
                size="sm" 
                onClick={onRetry}
                className="mt-3 gap-2"
              >
                <RefreshCw className="w-3 h-3" />
                Retry
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Default variant
  return (
    <div className={`flex flex-col items-center justify-center ${compact ? 'py-4' : 'py-8'} space-y-4`}>
      <div className="bg-destructive/10 p-3 rounded-full">
        <AlertTriangle className={`${compact ? 'w-6 h-6' : 'w-8 h-8'} text-destructive`} />
      </div>
      <div className="text-center space-y-1">
        <p className={`${compact ? 'text-sm' : 'text-base'} font-medium text-destructive`}>
          {message}
        </p>
        {details && process.env.NODE_ENV === 'development' && (
          <p className="text-xs text-muted-foreground max-w-md">{details}</p>
        )}
      </div>
      {onRetry && (
        <Button variant="outline" size={compact ? 'sm' : 'default'} onClick={onRetry} className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Retry
        </Button>
      )}
    </div>
  );
}

// ==================== Empty States ====================

export interface EmptyStateProps {
  /** 提示信息 */
  message?: string;
  /** 描述 */
  description?: string;
  /** 图标 */
  icon?: React.ReactNode;
  /** 操作按钮 */
  action?: {
    label: string;
    onClick: () => void;
  };
  /** 是否紧凑模式 */
  compact?: boolean;
}

/**
 * 空状态组件
 */
export function EmptyState({
  message = 'No data available',
  description,
  icon,
  action,
  compact = false
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center ${compact ? 'py-4' : 'py-8'} space-y-3`}>
      <div className="text-muted-foreground">
        {icon || <Inbox className={compact ? 'w-8 h-8' : 'w-12 h-12'} />}
      </div>
      <div className="text-center space-y-1">
        <p className={`${compact ? 'text-sm' : 'text-base'} font-medium text-muted-foreground`}>
          {message}
        </p>
        {description && (
          <p className="text-xs text-muted-foreground/70 max-w-md">{description}</p>
        )}
      </div>
      {action && (
        <Button variant="outline" size={compact ? 'sm' : 'default'} onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}

// ==================== AsyncBoundary ====================

export interface AsyncBoundaryProps<T> {
  /** 是否正在加载 */
  loading: boolean;
  /** 错误对象 */
  error: Error | null;
  /** 数据 */
  data: T | null;
  /** 子元素（渲染函数或 ReactNode） */
  children: React.ReactNode | ((data: T) => React.ReactNode);
  /** 加载状态自定义渲染 */
  loadingFallback?: React.ReactNode;
  /** 错误状态自定义渲染 */
  errorFallback?: React.ReactNode | ((error: Error) => React.ReactNode);
  /** 空状态自定义渲染 */
  emptyFallback?: React.ReactNode;
  /** 重试回调 */
  onRetry?: () => void;
  /** 自定义判断数据是否为空 */
  isEmpty?: (data: T) => boolean;
  /** 加载组件高度 */
  loadingHeight?: number | string;
  /** 加载变体 */
  loadingVariant?: LoadingSkeletonProps['variant'];
  /** 是否紧凑模式 */
  compact?: boolean;
}

/**
 * 异步边界组件 - 统一处理加载、错误、空状态
 */
export function AsyncBoundary<T>({
  loading,
  error,
  data,
  children,
  loadingFallback,
  errorFallback,
  emptyFallback,
  onRetry,
  isEmpty,
  loadingHeight = 200,
  loadingVariant = 'card',
  compact = false
}: AsyncBoundaryProps<T>) {
  // 加载状态
  if (loading && data === null) {
    if (loadingFallback) return <>{loadingFallback}</>;
    return <LoadingSkeleton height={loadingHeight} variant={loadingVariant} />;
  }

  // 错误状态
  if (error) {
    if (errorFallback) {
      return <>{typeof errorFallback === 'function' ? errorFallback(error) : errorFallback}</>;
    }
    return (
      <ErrorState 
        message={error.message} 
        onRetry={onRetry}
        compact={compact}
      />
    );
  }

  // 空状态
  const isDataEmpty = isEmpty ? isEmpty(data as T) : (
    data === null || 
    data === undefined || 
    (Array.isArray(data) && data.length === 0)
  );

  if (isDataEmpty) {
    if (emptyFallback) return <>{emptyFallback}</>;
    return <EmptyState compact={compact} />;
  }

  // 正常渲染
  if (typeof children === 'function') {
    return <>{children(data as T)}</>;
  }

  return <>{children}</>;
}

export default AsyncBoundary;
