'use client';

/**
 * AttentionChartContainer - 注意力图表容器组件
 * 
 * 演示新架构的用法：
 * 1. 使用 attentionService 获取数据
 * 2. 使用 useAsync hook 管理状态  
 * 3. 使用 AsyncBoundary 统一处理加载/错误/空状态
 */

import React from 'react';
import { useAsync } from '@/lib/hooks';
import { attentionService } from '@/lib/services';
import { AsyncBoundary } from '@/components/ui/async-boundary';
import AttentionChart from '@/components/AttentionChart';
import type { Time } from 'lightweight-charts';

interface AttentionChartContainerProps {
  symbol: string;
  height?: number;
  /** 开始日期 */
  start?: string;
  /** 结束日期 */
  end?: string;
  /** Crosshair 同步回调 */
  onCrosshairMove?: (time: Time | null) => void;
}

/**
 * 注意力图表容器
 */
export function AttentionChartContainer({ 
  symbol, 
  height = 250,
  start,
  end,
  onCrosshairMove,
}: AttentionChartContainerProps) {
  // 使用服务层获取数据
  const { data, loading, error, refresh } = useAsync(
    () => attentionService.getAttentionData(symbol, { start, end }),
    [symbol, start, end],
    { keepPreviousData: true }
  );

  // 将领域模型转换为组件期望的格式
  const chartData = data?.points.map(p => ({
    timestamp: p.timestamp,
    datetime: p.datetime,
    attention_score: p.attentionScore,
    news_count: p.newsCount,
    composite_attention_score: p.compositeAttentionScore,
    // 其他字段按需映射
  })) ?? [];

  return (
    <div className="space-y-2">
      {/* 可选：显示摘要信息 */}
      {data && (
        <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
          <span>
            Current: {data.summary.currentScore.toFixed(1)}
            <span className="mx-2">|</span>
            Avg: {data.summary.avgScore.toFixed(1)}
          </span>
          <span className={
            data.summary.trend === 'rising' ? 'text-green-500' :
            data.summary.trend === 'falling' ? 'text-red-500' :
            'text-muted-foreground'
          }>
            {data.summary.trend === 'rising' ? '↑' : 
             data.summary.trend === 'falling' ? '↓' : '→'} 
            {data.summary.trend}
          </span>
        </div>
      )}
      
      <AsyncBoundary
        loading={loading}
        error={error}
        data={chartData}
        onRetry={refresh}
        loadingHeight={height}
        loadingVariant="chart"
        isEmpty={(d) => d.length === 0}
        emptyFallback={
          <div 
            className="flex items-center justify-center text-muted-foreground bg-muted/30 rounded-lg"
            style={{ height }}
          >
            <span className="text-sm">No attention data available for {symbol}</span>
          </div>
        }
      >
        <AttentionChart 
          attentionData={chartData}
          height={height}
          onCrosshairMove={onCrosshairMove}
        />
      </AsyncBoundary>
    </div>
  );
}

export default AttentionChartContainer;
