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
    // 用于防止循环：标记是否是程序内部设置的 range
    const isSettingRangeRef = useRef(false)
    
    // 使用 ref 存储回调，避免图表重建
    const onVisibleRangeChangeRef = useRef(onVisibleRangeChange)
    const onCrosshairMoveRef = useRef(onCrosshairMove)
    
    // 更新 ref
    useEffect(() => {
      onVisibleRangeChangeRef.current = onVisibleRangeChange
      onCrosshairMoveRef.current = onCrosshairMove
    }, [onVisibleRangeChange, onCrosshairMove])

    // Memoize data transformation
    const attentionChartData = useMemo(() => {
      const result = attentionData.map((d) => ({
        time: Math.floor(d.timestamp / 1000) as any,
        value: (d.composite_attention_score ?? d.attention_score ?? 0),
      }))
      return result
    }, [attentionData])

    // 数据是否为空
    const hasData = attentionChartData && attentionChartData.length > 0

    useImperativeHandle(ref, () => ({
      setVisibleRange: (range: Range<Time>) => {
        if (isDisposedRef.current) return
        if (chartRef.current && range) {
          try {
            isSettingRangeRef.current = true
            chartRef.current.timeScale().setVisibleRange(range)
            setTimeout(() => { isSettingRangeRef.current = false }, 0)
          } catch (err) {
            isSettingRangeRef.current = false
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
        // 如果是程序内部设置的 range，跳过广播避免循环
        if (isSettingRangeRef.current) return
        
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
          // 窗口尺寸已更新
          if (newWidth <= 0) return
          chartRef.current.applyOptions({ width: newWidth })
          // Force fit content on resize
          chartRef.current.timeScale().fitContent()
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
      isDisposedRef.current = false

      return () => {
        isDisposedRef.current = true
        resizeObserver.disconnect()
        window.removeEventListener('resize', handleWindowResize)
        chart.remove()
        chartRef.current = null
        lineSeriesRef.current = null
      }
    }, [height, attentionChartData.length]) // 高度或数据长度变化时重建图表

    // Update data
    useEffect(() => {
      if (isDisposedRef.current) return
      if (!lineSeriesRef.current || !chartRef.current) return

      try {
        // Ensure data is sorted by time (lightweight-charts requirement)
        const sortedData = [...attentionChartData].sort((a, b) => (a.time as number) - (b.time as number))
        
        // Filter out invalid data points
        const validData = sortedData.filter(d => 
          d.time !== undefined && 
          !isNaN(d.time as number) && 
          d.value !== undefined && 
          !isNaN(d.value)
        )

        // Deduplicate time points (keep last)
        const uniqueDataMap = new Map();
        validData.forEach(d => uniqueDataMap.set(d.time, d));
        const uniqueData = Array.from(uniqueDataMap.values()).sort((a: any, b: any) => a.time - b.time);

        // 图表数据已更新
        if (uniqueData.length > 0) {
          // 数据范围和值范围已设置
        }

        lineSeriesRef.current.setData(uniqueData)

        // Fit content - 只有在有数据时才执行
        if (uniqueData.length > 0) {
          // Use setTimeout to ensure layout is complete
          setTimeout(() => {
            if (chartRef.current) {
              try {
                // 适配内容
                chartRef.current.timeScale().fitContent()
              } catch (e) {
                console.warn('[AttentionChart] fitContent failed', e)
              }
            }
          }, 100)
        }
      } catch (err) {
        console.warn('[AttentionChart] Failed to set data:', err)
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
      <div className="relative w-full bg-card/50" style={{ height }}>
        <div ref={chartContainerRef} className="w-full h-full" />
      </div>
    )
  }
)

AttentionChart.displayName = 'AttentionChart'

export default AttentionChart
