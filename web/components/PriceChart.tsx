'use client'

import React, { useEffect, useRef, useImperativeHandle, forwardRef, useState, useMemo, useCallback } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, Range, Time } from 'lightweight-charts'
import type { PriceCandle, AttentionEvent } from '@/lib/api'
import { Button } from '@/components/ui/button'

interface PriceChartProps {
  priceData: PriceCandle[]
  height?: number
  onVisibleRangeChange?: (range: Range<Time> | null) => void
  events?: AttentionEvent[]
  // Controlled state props
  volumeRatio?: number
  onVolumeRatioChange?: (ratio: number) => void
  showEventMarkers?: boolean
  onShowEventMarkersChange?: (show: boolean) => void
  // Crosshair sync
  onCrosshairMove?: (time: Time | null) => void
  // Hide controls (for MarketOverview page)
  hideControls?: boolean
}

export interface PriceChartRef {
  setVisibleRange: (range: Range<Time>) => void
  setCrosshair: (time: Time | null) => void
}

const PriceChart = forwardRef<PriceChartRef, PriceChartProps>(
  ({ 
    priceData, 
    height = 600, 
    onVisibleRangeChange, 
    events = [], 
    volumeRatio = 0.25,
    onVolumeRatioChange,
    showEventMarkers = true,
    onShowEventMarkersChange,
    onCrosshairMove,
    hideControls = false
  }, ref) => {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
    const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
    const isDisposedRef = useRef(false)

    // 数据是否为空
    const hasData = priceData && priceData.length > 0

    useImperativeHandle(ref, () => ({
      setVisibleRange: (range: Range<Time>) => {
        if (isDisposedRef.current) return
        if (chartRef.current && range) {
          try {
            chartRef.current.timeScale().setVisibleRange(range)
          } catch (err) {
            console.warn('[PriceChart] Failed to set visible range:', err)
          }
        }
      },
      setCrosshair: (time: Time | null) => {
        if (isDisposedRef.current) return
        if (chartRef.current && candlestickSeriesRef.current) {
          try {
            if (time) {
              // Find point by matching timestamp (seconds)
              const point = priceData.find(d => 
                Math.floor(d.timestamp / 1000) === (time as number)
              )
              const price = point ? point.close : 0
              chartRef.current.setCrosshairPosition(price, time, candlestickSeriesRef.current);
            } else {
              chartRef.current.clearCrosshairPosition();
            }
          } catch (err) {
            // Chart may be disposed, ignore
          }
        }
      }
    }))

  // 使用 ref 存储回调，避免图表重建
  const onVisibleRangeChangeRef = useRef(onVisibleRangeChange)
  const onCrosshairMoveRef = useRef(onCrosshairMove)
  
  // 更新 ref
  useEffect(() => {
    onVisibleRangeChangeRef.current = onVisibleRangeChange
    onCrosshairMoveRef.current = onCrosshairMove
  }, [onVisibleRangeChange, onCrosshairMove])

  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0a0e27' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#2B2B43',
      },
      rightPriceScale: {
        borderColor: '#2B2B43',
      },
      crosshair: {
        mode: 1, // CrosshairMode.Normal
      },
    })

    chartRef.current = chart

    // Add candlestick series
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    })
    candlestickSeriesRef.current = candlestickSeries

    // Add volume series
    const volumeSeries = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '',
    })
    volumeSeriesRef.current = volumeSeries

    // Subscribe to visible range changes - 使用 ref 避免重建
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      const visibleRange = chart.timeScale().getVisibleRange()
      if (onVisibleRangeChangeRef.current) {
        onVisibleRangeChangeRef.current(visibleRange)
      }
      // 广播到全局以便其他图表同步
      try {
        window.dispatchEvent(new CustomEvent('charts:setVisibleRange', { detail: visibleRange }))
      } catch {}
    })

    // Subscribe to crosshair moves - 使用 ref 避免重建
    chart.subscribeCrosshairMove((param) => {
      if (onCrosshairMoveRef.current) {
        onCrosshairMoveRef.current(param.time || null)
      }
    })

    // Handle resize with ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length === 0 || !entries[0].contentRect) return
      if (chartRef.current && chartContainerRef.current) {
        const newWidth = chartContainerRef.current.clientWidth
        if (newWidth > 0) {
          chartRef.current.applyOptions({ width: newWidth })
        }
      }
    })

    if (chartContainerRef.current) {
      resizeObserver.observe(chartContainerRef.current)
    }

    // Also listen to window resize as backup/for layout shifts
    const handleWindowResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }
    window.addEventListener('resize', handleWindowResize)

    // 订阅全局可视范围事件以进行同步
    const handleGlobalRange = (e: Event) => {
      const ce = e as CustomEvent
      const range = ce.detail as Range<Time>
      try {
        if (!isDisposedRef.current && chartRef.current && range) {
          chartRef.current.timeScale().setVisibleRange(range)
        }
      } catch {}
    }
    window.addEventListener('charts:setVisibleRange', handleGlobalRange as EventListener)
    isDisposedRef.current = false

    return () => {
      isDisposedRef.current = true
      resizeObserver.disconnect()
      window.removeEventListener('resize', handleWindowResize)
      window.removeEventListener('charts:setVisibleRange', handleGlobalRange as EventListener)
      chart.remove()
      chartRef.current = null
      candlestickSeriesRef.current = null
      volumeSeriesRef.current = null
    }
  }, [height]) // 只依赖 height，回调通过 ref 处理

  // Update volume ratio
  useEffect(() => {
    if (isDisposedRef.current) return
    if (chartRef.current) {
      try {
        chartRef.current.priceScale('').applyOptions({
          scaleMargins: {
            top: 1 - volumeRatio,
            bottom: 0,
          },
        })
      } catch (err) {
        // Chart may be disposed, ignore
      }
    }
  }, [volumeRatio])

  // Memoize data transformations to avoid recalculating on every render
  const { candleData, volumeData } = useMemo(() => {
    const candles = priceData.map((d) => ({
      time: Math.floor(d.timestamp / 1000) as any,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))

    const volumes = priceData.map((d) => ({
      time: Math.floor(d.timestamp / 1000) as any,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
    }))

    return { candleData: candles, volumeData: volumes }
  }, [priceData])

  // Memoize event markers
  const eventMarkers = useMemo(() => {
    if (!showEventMarkers || !events || events.length === 0 || !priceData || priceData.length === 0) return []
    
    const markers: any[] = []
    
    // Sort price data by timestamp just in case, though it should be sorted
    const sortedPriceData = [...priceData].sort((a, b) => a.timestamp - b.timestamp)
    
    events.forEach((e) => {
      const dt = new Date(e.datetime)
      const eventTime = Math.floor(dt.getTime() / 1000)
      
      // Find the candle that corresponds to this event
      // We look for the latest candle that started before or at the event time
      // This handles events that happen in the middle of a candle (e.g. 4h or 1d candle)
      
      // Find the last candle with timestamp <= eventTime
      let matchedTime: number | null = null
      
      // Optimization: Since events and price are usually sorted, we could optimize.
      // But for < 1000 items, simple search is fine.
      // We search from the end because events are usually recent.
      for (let i = sortedPriceData.length - 1; i >= 0; i--) {
        const candleTime = Math.floor(sortedPriceData[i].timestamp / 1000)
        if (candleTime <= eventTime) {
          // Check if it's "close enough" to be relevant (e.g. within 24h or the implied timeframe)
          // If the event is way after the last candle, we shouldn't mark it on the last candle.
          // But here we found a candle BEFORE the event.
          // We just need to make sure the event isn't too far ahead of this candle (e.g. gap in data).
          // Let's assume if it's within 1 week it's fine (for daily data with gaps).
          // Actually, for visualization, snapping to the previous candle is standard.
          matchedTime = candleTime
          break
        }
      }
      
      if (matchedTime) {
        let position: 'aboveBar' | 'belowBar' = 'aboveBar'
        let color = '#f59e0b'
        let shape: 'arrowUp' | 'arrowDown' | 'circle' = 'circle'
        let text = 'E'

        switch (e.event_type) {
          case 'high_bullish':
            position = 'aboveBar'
            color = '#22c55e'
            shape = 'arrowUp'
            text = 'Bull'
            break
          case 'high_bearish':
            position = 'belowBar'
            color = '#ef4444'
            shape = 'arrowDown'
            text = 'Bear'
            break
          case 'high_weighted_event':
            position = 'aboveBar'
            color = '#3b82f6'
            shape = 'circle'
            text = 'Wt'
            break
          case 'attention_spike':
            position = 'aboveBar'
            color = '#f59e0b'
            shape = 'circle'
            text = 'Spike'
            break
          case 'event_intensity':
            position = 'aboveBar'
            color = '#eab308'
            shape = 'circle'
            text = 'Evt'
            break
        }

        markers.push({ time: matchedTime, position, color, shape, text })
      }
    })
    
    // Deduplicate markers at the same time (lightweight-charts doesn't like duplicates)
    // If multiple events map to the same candle, we might want to show just one or combine them.
    // For now, just take the last one (or first one).
    // Better: Filter duplicates.
    // const uniqueMarkers = new Map()
    // markers.forEach(m => {
    //   // If we already have a marker at this time, maybe prioritize 'Spike' or 'Bull/Bear'?
    //   // For simplicity, just overwrite.
    //   uniqueMarkers.set(m.time, m)
    // })
    
    // const finalMarkers = Array.from(uniqueMarkers.values()).sort((a: any, b: any) => a.time - b.time)
    
    // Allow multiple markers (lightweight-charts supports array sorted by time)
    const finalMarkers = markers.sort((a: any, b: any) => a.time - b.time)
    console.log(`[PriceChart] Generated ${finalMarkers.length} markers from ${events.length} events (matched ${markers.length} raw)`)
    return finalMarkers
  }, [events, showEventMarkers, priceData])

  // Update data & markers
  useEffect(() => {
    if (isDisposedRef.current) return
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current) return

    try {
      candlestickSeriesRef.current.setData(candleData)
      volumeSeriesRef.current.setData(volumeData)

      // Set event markers
      if (candlestickSeriesRef.current) {
        console.log(`[PriceChart] Setting ${eventMarkers.length} markers`)
        candlestickSeriesRef.current.setMarkers(eventMarkers)
      }

      // Fit content - 只有在有数据时才执行
      if (chartRef.current && candleData.length > 0) {
        chartRef.current.timeScale().fitContent()
      }
    } catch (err) {
      // Chart may be disposed, ignore
    }
  }, [candleData, volumeData, eventMarkers])

  return (
    <div className="relative w-full" style={{ height }}>
      {/* Controls - hidden when hideControls is true */}
      {!hideControls && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-muted-foreground">成交量窗格:</span>
          <Button
            variant={volumeRatio === 0.2 ? 'default' : 'outline'}
            size="sm"
            onClick={() => onVolumeRatioChange?.(0.2)}
            className="text-xs h-6 px-2"
          >
            1/5
          </Button>
          <Button
            variant={volumeRatio === 0.25 ? 'default' : 'outline'}
            size="sm"
            onClick={() => onVolumeRatioChange?.(0.25)}
            className="text-xs h-6 px-2"
          >
            1/4
          </Button>
          <Button
            variant={volumeRatio === 0.33 ? 'default' : 'outline'}
            size="sm"
            onClick={() => onVolumeRatioChange?.(0.33)}
            className="text-xs h-6 px-2"
          >
            1/3
          </Button>
          <div className="mx-2 h-4 w-px bg-border" />
          <span className="text-xs text-muted-foreground">事件标注:</span>
          <Button
            variant={showEventMarkers ? 'default' : 'outline'}
            size="sm"
            onClick={() => onShowEventMarkersChange?.(true)}
            className="text-xs h-6 px-2"
          >
            开
          </Button>
          <Button
            variant={!showEventMarkers ? 'default' : 'outline'}
            size="sm"
            onClick={() => onShowEventMarkersChange?.(false)}
            className="text-xs h-6 px-2"
          >
            关
          </Button>
        </div>
      )}
      {/* 如果没有数据，显示占位符 */}
      {!hasData ? (
        <div 
          className="relative w-full flex items-center justify-center text-muted-foreground bg-card/50 rounded"
          style={{ height }}
        >
          <span className="text-sm">No price data available</span>
        </div>
      ) : (
        <div ref={chartContainerRef} className="w-full h-full" />
      )}
    </div>
  )
})

PriceChart.displayName = 'PriceChart'

export default PriceChart
