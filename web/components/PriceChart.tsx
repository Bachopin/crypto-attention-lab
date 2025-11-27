'use client'

import React, { useEffect, useRef, useImperativeHandle, forwardRef, useState } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, Range, Time } from 'lightweight-charts'
import type { PriceCandle } from '@/lib/api'
import { Button } from '@/components/ui/button'

interface PriceChartProps {
  priceData: PriceCandle[]
  height?: number
  onVisibleRangeChange?: (range: Range<Time> | null) => void
}

export interface PriceChartRef {
  setVisibleRange: (range: Range<Time>) => void
}

const PriceChart = forwardRef<PriceChartRef, PriceChartProps>(
  ({ priceData, height = 600, onVisibleRangeChange }, ref) => {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
    const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
    const [volumeRatio, setVolumeRatio] = useState(0.25) // 默认 1/4

    useImperativeHandle(ref, () => ({
      setVisibleRange: (range: Range<Time>) => {
        if (chartRef.current) {
          chartRef.current.timeScale().setVisibleRange(range)
        }
      },
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
      },
      crosshair: {
        mode: 1,
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

    // Add volume series (占比约 1/4)
    const volumeSeries = chart.addHistogramSeries({
      color: '#26a69a',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '',
    })
    volumeSeriesRef.current = volumeSeries

    // Configure volume scale margins dynamically
    chart.priceScale('').applyOptions({
      scaleMargins: {
        top: 1 - volumeRatio,
        bottom: 0,
      },
    })

    // Subscribe to visible range changes
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      const visibleRange = chart.timeScale().getVisibleRange()
      if (onVisibleRangeChange) {
        onVisibleRangeChange(visibleRange)
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
  }, [height, onVisibleRangeChange, volumeRatio])

  // Update data
  useEffect(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current) return

    // Convert price data (adjust for local timezone)
    // lightweight-charts treats time as UTC, so we offset by timezone
    const timezoneOffsetMinutes = new Date().getTimezoneOffset()
    
    const candleData = priceData.map((d) => ({
      time: Math.floor(d.timestamp / 1000 - timezoneOffsetMinutes * 60) as any,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))

    const volumeData = priceData.map((d) => ({
      time: Math.floor(d.timestamp / 1000 - timezoneOffsetMinutes * 60) as any,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
    }))

    candlestickSeriesRef.current.setData(candleData)
    volumeSeriesRef.current.setData(volumeData)

    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [priceData])

  return (
    <div className="relative w-full">
      {/* Volume Ratio Control */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-muted-foreground">成交量窗格:</span>
        <Button
          variant={volumeRatio === 0.2 ? 'default' : 'outline'}
          size="sm"
          onClick={() => setVolumeRatio(0.2)}
          className="text-xs h-6 px-2"
        >
          1/5
        </Button>
        <Button
          variant={volumeRatio === 0.25 ? 'default' : 'outline'}
          size="sm"
          onClick={() => setVolumeRatio(0.25)}
          className="text-xs h-6 px-2"
        >
          1/4
        </Button>
        <Button
          variant={volumeRatio === 0.33 ? 'default' : 'outline'}
          size="sm"
          onClick={() => setVolumeRatio(0.33)}
          className="text-xs h-6 px-2"
        >
          1/3
        </Button>
      </div>
      <div ref={chartContainerRef} className="w-full" />
    </div>
  )
})

PriceChart.displayName = 'PriceChart'

export default PriceChart
