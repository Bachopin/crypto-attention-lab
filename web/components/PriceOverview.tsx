'use client'

import React, { useEffect, useRef } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi } from 'lightweight-charts'
import type { PriceCandle } from '@/lib/api'

interface PriceOverviewProps {
  priceData: PriceCandle[]
  height?: number
}

export default function PriceOverview({ priceData, height = 192 }: PriceOverviewProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const lineSeriesRef = useRef<ISeriesApi<'Area'> | null>(null)

  // 如果没有数据，显示占位符
  if (!priceData || priceData.length === 0) {
    return (
      <div 
        className="relative w-full flex items-center justify-center text-muted-foreground"
        style={{ height }}
      >
        <span className="text-sm">Loading chart data...</span>
      </div>
    )
  }

  return <PriceOverviewChart priceData={priceData} height={height} />
}

function PriceOverviewChart({ priceData, height }: { priceData: PriceCandle[], height: number }) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const lineSeriesRef = useRef<ISeriesApi<'Area'> | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#1f2937', style: 1 },
      },
      width: chartContainerRef.current.clientWidth,
      height: height,
      timeScale: {
        visible: true,
        timeVisible: false,
        secondsVisible: false,
        borderColor: '#1f2937',
      },
      rightPriceScale: {
        borderColor: '#1f2937',
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
      },
      crosshair: {
        horzLine: {
          visible: false,
        },
        vertLine: {
          labelVisible: false,
        },
      },
      // Disable interaction (no drag/zoom)
      handleScroll: false,
      handleScale: false,
    })

    chartRef.current = chart

    // Add area series (filled line chart)
    const lineSeries = chart.addAreaSeries({
      lineColor: '#3b82f6',
      topColor: 'rgba(59, 130, 246, 0.4)',
      bottomColor: 'rgba(59, 130, 246, 0.0)',
      lineWidth: 2,
    })
    lineSeriesRef.current = lineSeries

    // Handle resize with ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      if (entries.length === 0 || !entries[0].contentRect) return
      if (chartRef.current && chartContainerRef.current) {
        const newWidth = chartContainerRef.current.clientWidth
        if (newWidth > 0) {
          chartRef.current.applyOptions({ width: newWidth })
          // Ensure content fits after resize (especially when switching from hidden tab)
          chartRef.current.timeScale().fitContent()
        }
      }
    })

    if (chartContainerRef.current) {
      resizeObserver.observe(chartContainerRef.current)
    }

    // Also listen to window resize as backup
    const handleWindowResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        })
      }
    }

    window.addEventListener('resize', handleWindowResize)

    return () => {
      resizeObserver.disconnect()
      window.removeEventListener('resize', handleWindowResize)
      chart.remove()
    }
  }, [height])

  // Update data
  useEffect(() => {
    if (!lineSeriesRef.current) return

    // Convert price data to simple line (use close price)
    // Lightweight charts expects UTC timestamp in seconds
    const lineData = priceData.map((d) => ({
      time: Math.floor(d.timestamp / 1000) as any,
      value: d.close,
    }))

    lineSeriesRef.current.setData(lineData)

    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [priceData])

  return (
    <div className="relative w-full">
      <div ref={chartContainerRef} className="w-full" />
    </div>
  )
}
