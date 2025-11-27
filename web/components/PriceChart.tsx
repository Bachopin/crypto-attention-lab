'use client'

import React, { useEffect, useRef, useImperativeHandle, forwardRef, useState, useMemo } from 'react'
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
    onCrosshairMove
  }, ref) => {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
    const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)

    useImperativeHandle(ref, () => ({
      setVisibleRange: (range: Range<Time>) => {
        if (chartRef.current && range) {
          try {
            chartRef.current.timeScale().setVisibleRange(range)
          } catch (err) {
            console.warn('[PriceChart] Failed to set visible range:', err)
          }
        }
      },
      setCrosshair: (time: Time | null) => {
        if (chartRef.current && candlestickSeriesRef.current) {
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

  // Update volume ratio
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.priceScale('').applyOptions({
        scaleMargins: {
          top: 1 - volumeRatio,
          bottom: 0,
        },
      })
    }
  }, [volumeRatio])

  // Update data & markers
  useEffect(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current) return

    // Use UTC timestamps (seconds) - Chart library handles local time conversion by default
    const candleData = priceData.map((d) => ({
      time: Math.floor(d.timestamp / 1000) as any,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }))

    const volumeData = priceData.map((d) => ({
      time: Math.floor(d.timestamp / 1000) as any,
      value: d.volume,
      color: d.close >= d.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
    }))

    candlestickSeriesRef.current.setData(candleData)
    volumeSeriesRef.current.setData(volumeData)

    // Set event markers on candles
    if (candlestickSeriesRef.current) {
      if (showEventMarkers && events && events.length > 0) {
        const markers = events.map((e) => {
          const dt = new Date(e.datetime)
          const time = Math.floor(dt.getTime() / 1000) as any
          // Map event type to style
          let position: 'aboveBar' | 'belowBar' = 'aboveBar'
          let color = '#f59e0b' // amber for generic
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

          return {
            time,
            position,
            color,
            shape,
            text,
          } as any
        })
        candlestickSeriesRef.current.setMarkers(markers)
      } else {
        candlestickSeriesRef.current.setMarkers([])
      }
    }

    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent()
    }
  }, [priceData, events, showEventMarkers])

  return (
    <div className="relative w-full">
      {/* Controls */}
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
      <div ref={chartContainerRef} className="w-full" />
    </div>
  )
})

PriceChart.displayName = 'PriceChart'

export default PriceChart
