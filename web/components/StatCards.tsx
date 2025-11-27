'use client'

import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatNumber, formatPercentage, formatVolume } from '@/lib/utils'
import { TrendingUp, TrendingDown } from 'lucide-react'

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
}

export function SummaryCard({
  symbol,
  price,
  priceChange,
  priceChangeAbs,
  volume24h,
  attention,
}: SummaryCardProps) {
  const isPositive = priceChange >= 0

  return (
    <Card className="bg-gradient-to-br from-primary/10 to-primary/5 border-primary/20">
      <CardHeader>
        <CardTitle className="text-2xl">{symbol}</CardTitle>
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
            <div className="text-sm text-muted-foreground">24h Volume</div>
            <div className="text-xl font-semibold">{formatVolume(volume24h)}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Attention</div>
            <div className="text-xl font-semibold">{attention.toFixed(1)}/100</div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
