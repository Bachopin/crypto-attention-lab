'use client'

import React, { useEffect, useState } from 'react'
import { useRealtimePrice, type RealtimePriceData } from '@/lib/websocket'
import { cn } from '@/lib/utils'

interface RealtimePriceTickerProps {
  symbol: string
  className?: string
  showChange?: boolean
  size?: 'sm' | 'md' | 'lg'
}

/**
 * 实时价格行情组件
 * 通过 WebSocket 显示实时更新的价格
 */
export function RealtimePriceTicker({
  symbol,
  className,
  showChange = true,
  size = 'md',
}: RealtimePriceTickerProps) {
  const { data, status, lastUpdate } = useRealtimePrice(symbol)
  const [prevPrice, setPrevPrice] = useState<number | null>(null)
  const [priceDirection, setPriceDirection] = useState<'up' | 'down' | null>(null)
  const [flashClass, setFlashClass] = useState('')

  // 价格变化动画
  useEffect(() => {
    if (data && prevPrice !== null) {
      if (data.close > prevPrice) {
        setPriceDirection('up')
        setFlashClass('animate-flash-green')
      } else if (data.close < prevPrice) {
        setPriceDirection('down')
        setFlashClass('animate-flash-red')
      }

      // 移除动画类
      const timer = setTimeout(() => setFlashClass(''), 300)
      return () => clearTimeout(timer)
    }
    if (data) {
      setPrevPrice(data.close)
    }
  }, [data?.close])

  const sizeClasses = {
    sm: 'text-lg',
    md: 'text-2xl',
    lg: 'text-4xl',
  }

  const formatPrice = (price: number) => {
    if (price >= 1000) {
      return price.toLocaleString('en-US', { 
        minimumFractionDigits: 2, 
        maximumFractionDigits: 2 
      })
    }
    return price.toFixed(price < 1 ? 6 : 4)
  }

  if (status === 'disconnected' || status === 'connecting') {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <span className={cn('font-mono text-muted-foreground', sizeClasses[size])}>
          --
        </span>
        {status === 'connecting' && (
          <span className="text-xs text-yellow-500 animate-pulse">连接中...</span>
        )}
      </div>
    )
  }

  if (!data) {
    return (
      <div className={cn('flex items-center gap-2', className)}>
        <span className={cn('font-mono text-muted-foreground', sizeClasses[size])}>
          加载中...
        </span>
      </div>
    )
  }

  const changePercent = prevPrice 
    ? ((data.close - prevPrice) / prevPrice * 100)
    : 0

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <span
        className={cn(
          'font-mono font-semibold transition-colors',
          sizeClasses[size],
          flashClass,
          priceDirection === 'up' && 'text-green-500',
          priceDirection === 'down' && 'text-red-500'
        )}
      >
        ${formatPrice(data.close)}
      </span>
      
      {showChange && priceDirection && (
        <span
          className={cn(
            'text-sm font-medium',
            priceDirection === 'up' ? 'text-green-500' : 'text-red-500'
          )}
        >
          {priceDirection === 'up' ? '▲' : '▼'}
          {Math.abs(changePercent).toFixed(2)}%
        </span>
      )}

      {/* 实时指示器 */}
      <div className="flex items-center gap-1">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
        </span>
        <span className="text-xs text-muted-foreground">LIVE</span>
      </div>
    </div>
  )
}

interface RealtimePriceCardProps {
  symbol: string
  name?: string
  className?: string
}

/**
 * 实时价格卡片
 * 显示完整的实时价格信息
 */
export function RealtimePriceCard({
  symbol,
  name,
  className,
}: RealtimePriceCardProps) {
  const { data, status } = useRealtimePrice(symbol)

  const formatVolume = (volume: number) => {
    if (volume >= 1_000_000_000) {
      return `${(volume / 1_000_000_000).toFixed(2)}B`
    }
    if (volume >= 1_000_000) {
      return `${(volume / 1_000_000).toFixed(2)}M`
    }
    if (volume >= 1_000) {
      return `${(volume / 1_000).toFixed(2)}K`
    }
    return volume.toFixed(2)
  }

  return (
    <div
      className={cn(
        'p-4 rounded-lg bg-card border transition-all',
        status === 'connected' && 'border-green-500/20',
        className
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-semibold text-lg">{symbol}</h3>
          {name && <p className="text-sm text-muted-foreground">{name}</p>}
        </div>
        <div className="flex items-center gap-1">
          <span
            className={cn(
              'h-2 w-2 rounded-full',
              status === 'connected' ? 'bg-green-500' : 'bg-gray-500'
            )}
          />
          <span className="text-xs text-muted-foreground">
            {status === 'connected' ? 'LIVE' : status}
          </span>
        </div>
      </div>

      {data ? (
        <div className="space-y-2">
          <RealtimePriceTicker symbol={symbol} size="lg" showChange={false} />
          
          <div className="grid grid-cols-2 gap-2 mt-4 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">High</span>
              <span className="font-mono text-green-500">
                ${data.high.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Low</span>
              <span className="font-mono text-red-500">
                ${data.low.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Open</span>
              <span className="font-mono">${data.open.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Volume</span>
              <span className="font-mono">{formatVolume(data.volume)}</span>
            </div>
          </div>
        </div>
      ) : (
        <div className="h-24 flex items-center justify-center text-muted-foreground">
          {status === 'connecting' ? '连接中...' : '等待数据...'}
        </div>
      )}
    </div>
  )
}

export default RealtimePriceTicker
