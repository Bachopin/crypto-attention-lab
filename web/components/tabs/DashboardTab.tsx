"use client"

import React, { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { StatCard, SummaryCard } from '@/components/StatCards'
import PriceChart, { PriceChartRef } from '@/components/PriceChart'
import AttentionChart, { AttentionChartRef } from '@/components/AttentionChart'
import PriceOverview from '@/components/PriceOverview'
import NewsList from '@/components/NewsList'
import { BarChart3, TrendingUp } from 'lucide-react'
import type {
  Timeframe,
  PriceCandle,
  AttentionData,
  NewsItem,
  SummaryStats,
  AttentionEvent,
} from '@/lib/api'
import type { Range, Time } from 'lightweight-charts'
import { useSettings } from '@/components/SettingsProvider'

interface DashboardTabProps {
  selectedSymbol: string
  availableSymbols: string[]
  summaryStats: SummaryStats
  assetNewsData: NewsItem[]
  priceData: PriceCandle[]
  overviewPriceData: PriceCandle[]
  attentionData: AttentionData[]
  events: AttentionEvent[]
  selectedTimeframe: Timeframe
  timeframes: Timeframe[]
  onTimeframeChange: (tf: Timeframe) => void
  volumeRatio: number
  onVolumeRatioChange: (n: number) => void
  showEventMarkers: boolean
  onShowEventMarkersChange: (v: boolean) => void
  onSymbolChange: (sym: string) => void
  onRefresh: () => void
  updating: boolean
  updateCountdown: number
  priceChartRef: React.RefObject<PriceChartRef>
  attentionChartRef: React.RefObject<AttentionChartRef>
  onPriceRangeChange: (range: Range<Time> | null) => void
  onAttentionRangeChange: (range: Range<Time> | null) => void
  onCrosshairMove: (time: Time | null) => void
}

export default function DashboardTab(props: DashboardTabProps) {
  const {
    selectedSymbol,
    availableSymbols,
    summaryStats,
    assetNewsData,
    priceData,
    overviewPriceData,
    attentionData,
    events,
    selectedTimeframe,
    timeframes,
    onTimeframeChange,
    volumeRatio,
    onVolumeRatioChange,
    showEventMarkers,
    onShowEventMarkersChange,
    onSymbolChange,
    onRefresh,
    updating,
    updateCountdown,
    priceChartRef,
    attentionChartRef,
    onPriceRangeChange,
    onAttentionRangeChange,
    onCrosshairMove,
  } = props

  const { settings } = useSettings();

  // Update crosshair handler
  const handleCrosshairMoveWrapper = React.useCallback((time: Time | null) => {
    onCrosshairMove(time)
  }, [onCrosshairMove])

  return (
    <div className="space-y-6">
      {/* Section 1: Top Summary */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Summary Card */}
        <div className="lg:col-span-1">
          <SummaryCard
            symbol={`${selectedSymbol}/USDT`}
            price={summaryStats.current_price}
            priceChange={summaryStats.price_change_24h}
            priceChangeAbs={summaryStats.price_change_24h_abs}
            volume24h={summaryStats.volume_24h}
            attention={summaryStats.current_attention}
            selectedSymbol={selectedSymbol}
            availableSymbols={availableSymbols}
            onSymbolChange={onSymbolChange}
            onRefresh={onRefresh}
            updating={updating}
            updateCountdown={updateCountdown}
          />
        </div>

        {/* Stat Cards Grid */}
        <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="News Today" value={summaryStats.news_count_today} decimals={0} />
          <StatCard title="Avg Attention (7d)" value={summaryStats.avg_attention_7d} suffix="/100" />
          <StatCard title="30d Volatility" value={summaryStats.volatility_30d} suffix="%" />
          <StatCard title="24h Change" value={summaryStats.price_change_24h} change={summaryStats.price_change_24h} suffix="%" />
        </div>
      </section>

      {/* Section 2: Middle Panels */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Price Overview - Simple Line Chart */}
        <div className="bg-card rounded-lg border p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            Price Overview (90 Days)
          </h2>
          <PriceOverview priceData={overviewPriceData} height={192} />
        </div>

        {/* Recent News */}
        <NewsList news={assetNewsData} maxItems={5} title={`${selectedSymbol} RECENT NEWS`} />
      </section>

      {/* Section 3: Main Price Action Chart */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Price Action</h2>

          {/* Timeframe Selector */}
          <div className="flex gap-2">
            {timeframes.map((tf) => (
              <Button key={tf} variant={selectedTimeframe === tf ? 'default' : 'outline'} size="sm" onClick={() => onTimeframeChange(tf)}>
                {tf}
              </Button>
            ))}
          </div>
        </div>

        <div className="bg-card rounded-lg border p-4">
          <PriceChart
            ref={priceChartRef}
            priceData={priceData}
            height={500}
            onVisibleRangeChange={onPriceRangeChange}
            events={events}
            volumeRatio={volumeRatio}
            onVolumeRatioChange={onVolumeRatioChange}
            showEventMarkers={showEventMarkers}
            onShowEventMarkersChange={onShowEventMarkersChange}
            onCrosshairMove={handleCrosshairMoveWrapper}
          />
        </div>
      </section>

      {/* Section 4: Attention Score Chart */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-yellow-500" />
            Attention Score
          </h2>
        </div>

        <div className="bg-card rounded-lg border p-4">
          <AttentionChart
            ref={attentionChartRef}
            attentionData={attentionData}
            height={250}
            onVisibleRangeChange={onAttentionRangeChange}
            onCrosshairMove={onCrosshairMove}
          />
        </div>
      </section>
    </div>
  )
}
