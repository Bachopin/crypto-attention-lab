'use client'

/**
 * 市场概况 Tab - 主流币总览
 * 
 * 展示 BTC / ETH / BNB / SOL 四个主流币的长期 Attention 与行情
 * 
 * 优化：MajorAssetModule 内部已实现数据缓存，避免重复加载
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import MajorAssetModule from '@/components/MajorAssetModule'
import ErrorBoundary from '@/components/ErrorBoundary'
import { Calendar, Clock } from 'lucide-react'
import type { Timeframe } from '@/lib/api'
import { Time } from 'lightweight-charts'
import { useSettings } from '@/components/SettingsProvider'
import { useTabData } from '@/components/TabDataProvider'

// 主流币列表
const MAJOR_SYMBOLS = ['BTC', 'ETH', 'BNB', 'SOL'] as const

// 时间范围选项
type TimeRange = '3M' | '6M' | '1Y' | 'ALL'
const TIME_RANGES: TimeRange[] = ['3M', '6M', '1Y', 'ALL']

// 时间粒度选项
const TIMEFRAMES: Timeframe[] = ['1D', '4H']

// 根据时间范围计算 start date
function getStartDate(range: TimeRange): string | undefined {
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  
  switch (range) {
    case '3M':
      now.setMonth(now.getMonth() - 3)
      return now.toISOString()
    case '6M':
      now.setMonth(now.getMonth() - 6)
      return now.toISOString()
    case '1Y':
      now.setFullYear(now.getFullYear() - 1)
      return now.toISOString()
    case 'ALL':
    default:
      return undefined
  }
}

export default function MarketOverviewTab() {
  const { settings } = useSettings();
  const { setMarketOverviewLoaded } = useTabData();
  const [selectedTimeRange, setSelectedTimeRange] = useState<TimeRange>('6M')

  // Check if global setting is supported here
  const initialTimeframe = (settings.defaultTimeframe === '1D' || settings.defaultTimeframe === '4H') 
    ? settings.defaultTimeframe 
    : '1D';

  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>(initialTimeframe)
  const [crosshairTime, setCrosshairTime] = useState<Time | null>(null)

  const dateRange = useMemo(() => ({
    start: getStartDate(selectedTimeRange),
    end: undefined,
  }), [selectedTimeRange])

  const handleCrosshairMove = useCallback((time: Time | null) => {
    setCrosshairTime(time)
  }, [])
  
  // 标记 Tab 已加载
  useEffect(() => {
    setMarketOverviewLoaded(true);
  }, [setMarketOverviewLoaded]);

  return (
    <div className="space-y-4">
      {/* 控制面板 */}
      <div className="flex items-center justify-between flex-wrap gap-4 bg-card/50 rounded-lg p-3 border border-border/50">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">主流币市场总览</span>
          <span>·</span>
          <span>展示 BTC / ETH / BNB / SOL 的长期 Attention 与行情走势</span>
        </div>

        <div className="flex items-center gap-4">
          {/* 时间范围选择 */}
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">范围:</span>
            <div className="flex gap-1">
              {TIME_RANGES.map((range) => (
                <Button
                  key={range}
                  variant={selectedTimeRange === range ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedTimeRange(range)}
                  className="text-xs h-7 px-2"
                >
                  {range}
                </Button>
              ))}
            </div>
          </div>

          {/* 时间粒度选择 */}
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">粒度:</span>
            <div className="flex gap-1">
              {TIMEFRAMES.map((tf) => (
                <Button
                  key={tf}
                  variant={selectedTimeframe === tf ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setSelectedTimeframe(tf)}
                  className="text-xs h-7 px-2"
                >
                  {tf}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 四个主流币模块 */}
      <div className="space-y-4">
        {MAJOR_SYMBOLS.map((symbol) => (
          <ErrorBoundary
            key={`${symbol}-boundary`}
            fallback={
              <div className="bg-card/80 backdrop-blur border-border/50 rounded-lg p-8 text-center">
                <p className="text-red-500 font-medium">Failed to load {symbol} module</p>
                <p className="text-sm text-muted-foreground mt-2">Please refresh the page</p>
              </div>
            }
          >
            <MajorAssetModule
              key={symbol}
              symbol={symbol}
              timeframe={selectedTimeframe}
              dateRange={dateRange}
              onCrosshairMove={handleCrosshairMove}
              crosshairTime={crosshairTime}
            />
          </ErrorBoundary>
        ))}
      </div>
    </div>
  )
}
