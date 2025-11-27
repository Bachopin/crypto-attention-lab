'use client'

import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
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

    useImperativeHandle(ref, () => ({
      setVisibleRange: (range: Range<Time>) => {
        if (chartRef.current && range) {
          try {
            chartRef.current.timeScale().setVisibleRange(range)
          } catch (err) {
            console.warn('[AttentionChart] Failed to set visible range:', err)
          }
        }
      },
      setCrosshair: (time: Time | null) => {
        if (chartRef.current && lineSeriesRef.current) {
          if (time) {
            const point = attentionData.find(d => 
              Math.floor(d.timestamp / 1000) === (time as number)
            )
            const value = point ? point.attention_score : 0
            chartRef.current.setCrosshairPosition(value, time, lineSeriesRef.current);
          } else {
            chartRef.current.clearCrosshairPosition();
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

      // Add line series for attention score
      const lineSeries = chart.addLineSeries({
        color: '#fbbf24',
        lineWidth: 2,
        title: 'Attention Score',
        priceFormat: {
          type: 'custom',
          formatter: (price: number) => price.toFixed(1),
        },
      })
      lineSeriesRef.current = lineSeries

      // Subscribe to visible range changes
      chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
        const visibleRange = chart.timeScale().getVisibleRange()
        if (onVisibleRangeChange) {
          onVisibleRangeChange(visibleRange)
        }
      })

      // Subscribe to crosshair moves
      chart.subscribeCrosshairMove((param) => {
        if (onCrosshairMove) {
          onCrosshairMove(param.time || null)
        }
      })

      // Handle resize
      const handleResize = () => {
        if (chartContainerRef.current) {
          chart.applyOptions({
            width: chartContainerRef.current.clientWidth,
          })
        }
      }

      window.addEventListener('resize', handleResize)

      return () => {
        window.removeEventListener('resize', handleResize)
        chart.remove()
      }
    }, [height, onVisibleRangeChange, onCrosshairMove])

    // Update data
    useEffect(() => {
      if (!lineSeriesRef.current) return

      // Use UTC timestamps (seconds)
      const attentionChartData = attentionData.map((d) => ({
        time: Math.floor(d.timestamp / 1000) as any,
        value: d.attention_score,
      }))

      lineSeriesRef.current.setData(attentionChartData)

      // Fit content
      if (chartRef.current) {
        chartRef.current.timeScale().fitContent()
      }
    }, [attentionData])

    return (
      <div className="relative w-full">
        <div ref={chartContainerRef} className="w-full" />
      </div>
    )
  }
)

AttentionChart.displayName = 'AttentionChart'

export default AttentionChart
