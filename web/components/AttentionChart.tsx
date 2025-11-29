'use client'

import React, { useEffect, useRef, useImperativeHandle, forwardRef, useMemo } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, Range, Time } from 'lightweight-charts'
import type { AttentionData } from '@/lib/api'

interface AttentionChartProps {
  attentionData: AttentionData[]
  height?: number
  onVisibleRangeChange?: (range: Range<Time> | null) => void
  onCrosshairMove?: (time: Time | null) => void
}

export interface AttentionChartRef {
  setVisibleRange: (range: Range<Time>) => void
  setCrosshair: (time: Time | null) => void
}

const AttentionChart = forwardRef<AttentionChartRef, AttentionChartProps>(
  ({ attentionData, height = 200, onVisibleRangeChange, onCrosshairMove }, ref) => {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const lineSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
    const isDisposedRef = useRef(false)
    
    // 使用 ref 存储回调，避免图表重建
    const onVisibleRangeChangeRef = useRef(onVisibleRangeChange)
    const onCrosshairMoveRef = useRef(onCrosshairMove)
    
    // 更新 ref
    useEffect(() => {
      onVisibleRangeChangeRef.current = onVisibleRangeChange
      onCrosshairMoveRef.current = onCrosshairMove
    }, [onVisibleRangeChange, onCrosshairMove])

    // 数据是否为空
    const hasData = attentionData && attentionData.length > 0

    useImperativeHandle(ref, () => ({
      setVisibleRange: (range: Range<Time>) => {
        if (isDisposedRef.current) return
        if (chartRef.current && range) {
          try {
            chartRef.current.timeScale().setVisibleRange(range)
          } catch (err) {
            console.warn('[AttentionChart] Failed to set visible range:', err)
          }
        }
      },
      setCrosshair: (time: Time | null) => {
        if (isDisposedRef.current) return
        if (chartRef.current && lineSeriesRef.current) {
          try {
            if (time) {
              const point = attentionData.find(d => 
                Math.floor(d.timestamp / 1000) === (time as number)
              )
              const value = point
                ? (point.composite_attention_score ?? point.attention_score ?? 0)
                : 0
              chartRef.current.setCrosshairPosition(value, time, lineSeriesRef.current);
            } else {
              chartRef.current.clearCrosshairPosition();
            }
          } catch (err) {
            // Chart may be disposed, ignore
          }
        }
      }
    }))

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
          scaleMargins: {
            top: 0.1,
            bottom: 0.1,
          },
        },
        crosshair: {
          mode: 1,
        },
      })

      chartRef.current = chart

      // Add line series for attention score (prefer composite)
      const lineSeries = chart.addLineSeries({
        color: '#fbbf24',
        lineWidth: 2,
        title: 'Composite Attention',
        priceFormat: {
          type: 'custom',
          formatter: (price: number) => price.toFixed(1),
        },
      })
      lineSeriesRef.current = lineSeries

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

      // Also listen to window resize as backup
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
        lineSeriesRef.current = null
      }
    }, [height]) // 只依赖 height，回调通过 ref 处理

    // Memoize data transformation
    const attentionChartData = useMemo(() => {
      return attentionData.map((d) => ({
        time: Math.floor(d.timestamp / 1000) as any,
        value: (d.composite_attention_score ?? d.attention_score ?? 0),
      }))
    }, [attentionData])

    // Update data
    useEffect(() => {
      if (isDisposedRef.current) return
      if (!lineSeriesRef.current || !chartRef.current) return

      try {
        lineSeriesRef.current.setData(attentionChartData)

        // Fit content - 只有在有数据时才执行
        if (attentionChartData.length > 0) {
          chartRef.current.timeScale().fitContent()
        }
      } catch (err) {
        // Chart may be disposed, ignore
      }
    }, [attentionChartData])

    // 如果没有数据，显示占位符
    if (!hasData) {
      return (
        <div 
          className="relative w-full flex items-center justify-center text-muted-foreground bg-card/50 rounded"
          style={{ height }}
        >
          <span className="text-sm">No attention data available</span>
        </div>
      )
    }

    return (
      <div className="relative w-full">
        <div ref={chartContainerRef} className="w-full" />
      </div>
    )
  }
)

AttentionChart.displayName = 'AttentionChart'

export default AttentionChart
