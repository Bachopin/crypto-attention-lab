'use client'

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatNumber, formatPercentage, formatVolume } from '@/lib/utils'
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  change?: number
  suffix?: string
  decimals?: number
}

export function StatCard({ title, value, change, suffix = '', decimals = 2 }: StatCardProps) {
  const displayValue = typeof value === 'number' ? formatNumber(value, decimals) : value
  const showChange = change !== undefined && change !== null

  return (
    <Card className="bg-card/50 backdrop-blur">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline justify-between">
          <div className="text-2xl font-bold">
            {displayValue}
            {suffix && <span className="text-lg text-muted-foreground ml-1">{suffix}</span>}
          </div>
          {showChange && (
            <div
              className={`flex items-center text-sm font-medium ${
                change! >= 0 ? 'text-chart-green' : 'text-chart-red'
              }`}
            >
              {change! >= 0 ? (
                <TrendingUp className="w-4 h-4 mr-1" />
              ) : (
                <TrendingDown className="w-4 h-4 mr-1" />
              )}
              {formatPercentage(Math.abs(change!))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

interface SummaryCardProps {
  symbol: string
  price: number
  priceChange: number
  priceChangeAbs: number
  volume24h: number
  attention: number
  // 新增：集成控制
  selectedSymbol?: string
  availableSymbols?: string[]
  onSymbolChange?: (symbol: string) => void
  onRefresh?: () => void
  updating?: boolean
  updateCountdown?: number
}

export function SummaryCard({
  symbol,
  price,
  priceChange,
  priceChangeAbs,
  volume24h,
  attention,
  selectedSymbol,
  availableSymbols,
  onSymbolChange,
  onRefresh,
  updating = false,
  updateCountdown = 0,
}: SummaryCardProps) {
  const isPositive = priceChange >= 0

  return (
    <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-2xl">{symbol}</CardTitle>
          {onRefresh && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRefresh}
              disabled={updating}
              className="text-xs"
            >
              {updating ? (
                <span className="flex items-center gap-1.5">
                  <RefreshCw className="w-3 h-3 animate-spin" />
                  {updateCountdown > 0 ? `${updateCountdown}s` : '...'}
                </span>
              ) : (
                <span className="flex items-center gap-1.5">
                  <RefreshCw className="w-3 h-3" />
                  刷新
                </span>
              )}
            </Button>
          )}
        </div>
        {/* 资产选择器 */}
        {selectedSymbol && availableSymbols && onSymbolChange && (
          <select 
            value={selectedSymbol}
            onChange={(e) => onSymbolChange(e.target.value)}
            className="mt-2 w-full h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {availableSymbols.map(sym => (
              <option key={sym} value={sym}>{sym}/USDT</option>
            ))}
          </select>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="text-4xl font-bold">${formatNumber(price)}</div>
          <div className={`text-lg font-medium mt-1 ${isPositive ? 'text-chart-green' : 'text-chart-red'}`}>
            {isPositive ? '+' : ''}${formatNumber(priceChangeAbs)} ({formatPercentage(priceChange)})
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
          <div>
            <div className="text-sm text-muted-foreground cursor-help" title="24小时交易量（USDT计价），反映市场活跃程度">24h Volume ⓘ</div>
            <div className="text-xl font-semibold">{formatVolume(volume24h)}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground cursor-help" title="注意力分数 (0-100)：基于新闻、社交媒体等多维度数据的综合热度指标。50=平均水平，80+=高热度">Attention ⓘ</div>
            <div className="text-xl font-semibold">{attention.toFixed(1)}/100</div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
