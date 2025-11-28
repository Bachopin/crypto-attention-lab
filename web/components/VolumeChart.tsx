'use client'

import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, Range, Time } from 'lightweight-charts'
import type { PriceCandle } from '@/lib/api'

interface VolumeChartProps {
  priceData: PriceCandle[]
  height?: number
  onVisibleRangeChange?: (range: Range<Time> | null) => void
  onCrosshairMove?: (time: Time | null) => void
}

export interface VolumeChartRef {
  setVisibleRange: (range: Range<Time>) => void
  setCrosshair: (time: Time | null) => void
}

const VolumeChart = forwardRef<VolumeChartRef, VolumeChartProps>(
  ({ priceData, height = 150, onVisibleRangeChange, onCrosshairMove }, ref) => {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)

    useImperativeHandle(ref, () => ({
      setVisibleRange: (range: Range<Time>) => {
        if (chartRef.current && range) {
          try {
            chartRef.current.timeScale().setVisibleRange(range)
          } catch (err) {
            console.warn('[VolumeChart] Failed to set visible range:', err)
          }
        }
      },
      setCrosshair: (time: Time | null) => {
        if (chartRef.current && volumeSeriesRef.current) {
          if (time) {
            const point = priceData.find(d => 
              Math.floor(d.timestamp / 1000) === (time as number)
            )
            const value = point ? point.volume : 0
            chartRef.current.setCrosshairPosition(value, time, volumeSeriesRef.current);
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

      // Add volume series
      const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
          type: 'volume',
        },
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

    // Update data
    useEffect(() => {
      if (!volumeSeriesRef.current) return

      const volumeData = priceData.map((d) => ({
        time: Math.floor(d.timestamp / 1000) as any,
        value: d.volume,
        color: d.close >= d.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
      }))

      volumeSeriesRef.current.setData(volumeData)

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
)

VolumeChart.displayName = 'VolumeChart'

export default VolumeChart
