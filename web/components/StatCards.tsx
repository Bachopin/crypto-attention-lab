'use client'

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatNumber, formatPercentage, formatVolume } from '@/lib/utils'
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react'
import { RealtimePriceTicker } from '@/components/RealtimePrice'

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
  const isPositive = change !== undefined && change !== null && change >= 0

  return (
    <Card className="bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-sm border-border/50 group">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground transition-colors group-hover:text-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline justify-between">
          <div className="text-2xl font-bold transition-transform group-hover:scale-105">
            {displayValue}
            {suffix && <span className="text-lg text-muted-foreground ml-1">{suffix}</span>}
          </div>
          {showChange && (
            <div
              className={`flex items-center text-sm font-medium px-2 py-1 rounded-md transition-all ${
                isPositive 
                  ? 'text-chart-green bg-chart-green/10 group-hover:bg-chart-green/20' 
                  : 'text-chart-red bg-chart-red/10 group-hover:bg-chart-red/20'
              }`}
            >
              {isPositive ? (
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
  // 实时价格开关
  enableRealtimePrice?: boolean
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
  enableRealtimePrice = false,
}: SummaryCardProps) {
  const isPositive = priceChange >= 0

  return (
    <Card className="bg-gradient-to-br from-primary/20 via-primary/10 to-primary/5 border-primary/30 shadow-xl relative overflow-hidden group">
      {/* 装饰性渐变背景 */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-50 group-hover:opacity-75 transition-opacity duration-300"></div>
      <div className="relative z-10">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-2xl font-bold gradient-text">{symbol}</CardTitle>
            {onRefresh && (
              <Button
                variant="outline"
                size="sm"
                onClick={onRefresh}
                disabled={updating}
                className="text-xs bg-background/50 backdrop-blur-sm"
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
              className="mt-2 w-full h-9 rounded-md border border-input/50 bg-background/50 backdrop-blur-sm px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-all hover:border-primary/50"
            >
              {availableSymbols.map(sym => (
                <option key={sym} value={sym}>{sym}/USDT</option>
              ))}
            </select>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            {/* 实时价格（WebSocket）或静态价格（API 轮询） */}
            {enableRealtimePrice ? (
              <div className="space-y-1">
                {/* 从 "ZEC/USDT" 提取 "ZEC" 用于 WebSocket 订阅 */}
                <RealtimePriceTicker 
                  symbol={symbol.split('/')[0]} 
                  size="lg" 
                  showChange={false} 
                  initialPrice={price}
                />
                <div className={`text-lg font-medium px-2 py-1 rounded-md inline-block transition-all ${
                  isPositive 
                    ? 'text-chart-green bg-chart-green/10' 
                    : 'text-chart-red bg-chart-red/10'
                }`}>
                  {isPositive ? '+' : ''}${formatNumber(priceChangeAbs)} ({formatPercentage(priceChange)})
                </div>
              </div>
            ) : (
              <>
                <div className="text-4xl font-bold transition-transform group-hover:scale-105">${formatNumber(price)}</div>
                <div className={`text-lg font-medium mt-1 px-2 py-1 rounded-md inline-block transition-all ${
                  isPositive 
                    ? 'text-chart-green bg-chart-green/10' 
                    : 'text-chart-red bg-chart-red/10'
                }`}>
                  {isPositive ? '+' : ''}${formatNumber(priceChangeAbs)} ({formatPercentage(priceChange)})
                </div>
              </>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border/50">
            <div className="group/item">
              <div className="text-sm text-muted-foreground cursor-help transition-colors group-hover/item:text-foreground" title="24小时交易量（USDT计价），反映市场活跃程度">24h Volume ⓘ</div>
              <div className="text-xl font-semibold transition-transform group-hover/item:scale-105">{formatVolume(volume24h)}</div>
            </div>
            <div className="group/item">
              <div className="text-sm text-muted-foreground cursor-help transition-colors group-hover/item:text-foreground" title="注意力分数 (0-100)：基于新闻、社交媒体等多维度数据的综合热度指标。50=平均水平，80+=高热度">Attention ⓘ</div>
              <div className="text-xl font-semibold transition-transform group-hover/item:scale-105">{attention.toFixed(1)}/100</div>
            </div>
          </div>
        </CardContent>
      </div>
    </Card>
  )
}
