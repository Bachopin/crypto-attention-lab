'use client';

/**
 * PriceOverviewContainer - 价格概览容器组件
 * 
 * 演示新架构的用法：
 * 1. 使用服务层获取数据
 * 2. 使用 useAsync hook 管理状态
 * 3. 使用 AsyncBoundary 统一处理加载/错误/空状态
 * 
 * @example
 * ```tsx
 * <PriceOverviewContainer symbol="BTC" height={192} />
 * ```
 */

import React from 'react';
import { useAsync } from '@/lib/hooks';
import { priceService } from '@/lib/services';
import { AsyncBoundary, LoadingSkeleton } from '@/components/ui/async-boundary';
import PriceOverview from '@/components/PriceOverview';

interface PriceOverviewContainerProps {
  symbol: string;
  height?: number;
  /** 是否显示统计信息 */
  showStats?: boolean;
}

/**
 * 价格概览容器 - 负责数据获取，PriceOverview 负责渲染
 */
export function PriceOverviewContainer({ 
  symbol, 
  height = 192,
  showStats = false 
}: PriceOverviewContainerProps) {
  // 使用服务层 + useAsync 获取数据
  const { data, loading, error, refresh } = useAsync(
    () => priceService.getPriceOverview(symbol),
    [symbol],
    { keepPreviousData: true }
  );

  return (
    <div className="space-y-2">
      <AsyncBoundary
        loading={loading}
        error={error}
        data={data}
        onRetry={refresh}
        loadingHeight={height}
        loadingVariant="chart"
        isEmpty={(d) => !d || d.points.length === 0}
        emptyFallback={
          <div 
            className="flex items-center justify-center text-muted-foreground bg-muted/30 rounded-lg"
            style={{ height }}
          >
            <span className="text-sm">No price data available for {symbol}</span>
          </div>
        }
      >
        {(priceSeries) => (
          <>
            {/* 统计信息（可选） */}
            {showStats && (
              <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
                <span>{priceSeries.summary.days} days</span>
                <span className={priceSeries.summary.changePercent >= 0 ? 'text-green-500' : 'text-red-500'}>
                  {priceSeries.summary.changePercent >= 0 ? '+' : ''}
                  {priceSeries.summary.changePercent.toFixed(2)}%
                </span>
              </div>
            )}
            
            {/* 渲染图表 - 传入领域模型的 points */}
            <PriceOverview 
              priceData={priceSeries.points} 
              height={height} 
            />
          </>
        )}
      </AsyncBoundary>
    </div>
  );
}

export default PriceOverviewContainer;
