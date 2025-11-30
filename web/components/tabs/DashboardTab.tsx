"use client"

import React, { useState, useEffect, useMemo, useRef, useCallback, lazy, Suspense } from 'react'
import dynamic from 'next/dynamic'
import { Button } from '@/components/ui/button'
import { StatCard, SummaryCard } from '@/components/StatCards'
import { BarChart3, TrendingUp } from 'lucide-react'
import {
  fetchPrice,
  fetchAttention,
  fetchNews,
  fetchAttentionEvents,
  fetchSummaryStats,
  PriceCandle,
  AttentionData,
  NewsItem,
  AttentionEvent,
  Timeframe,
  SummaryStats
} from '@/lib/api'
import { dashboardService } from '@/lib/services/dashboard-service'
import type { Time } from 'lightweight-charts'
import type { PriceChartRef } from '@/components/PriceChart'
import type { AttentionChartRef } from '@/components/AttentionChart'

// Dynamic load heavy chart components
const PriceChart = dynamic(() => import('@/components/PriceChart'), {
  loading: () => <div className="h-[500px] w-full bg-muted/10 animate-pulse rounded-lg" />,
  ssr: false
})
const AttentionChart = dynamic(() => import('@/components/AttentionChart'), {
  loading: () => <div className="h-[250px] w-full bg-muted/10 animate-pulse rounded-lg" />,
  ssr: false
})
const PriceOverview = dynamic(() => import('@/components/PriceOverview'), {
  loading: () => <div className="h-[192px] w-full bg-muted/10 animate-pulse rounded-lg" />,
  ssr: false
})
const NewsList = dynamic(() => import('@/components/NewsList'), {
  loading: () => <div className="h-[400px] w-full bg-muted/10 animate-pulse rounded-lg" />
})

// Lazy load heavy analysis panels
const AttentionEvents = lazy(() => import('@/components/AttentionEvents'))
const BacktestPanel = lazy(() => import('@/components/BacktestPanel'))
const AttentionRegimePanel = lazy(() => import('@/components/AttentionRegimePanel'))

interface DashboardTabProps {
  symbol: string;
  availableSymbols: string[];
  onSymbolChange: (sym: string) => void;
}

export default function DashboardTab({ symbol, availableSymbols, onSymbolChange }: DashboardTabProps) {
  // State
  const [timeframe, setTimeframe] = useState<Timeframe>('1D');
  const [priceData, setPriceData] = useState<PriceCandle[]>([]);
  const [attentionData, setAttentionData] = useState<AttentionData[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [events, setEvents] = useState<AttentionEvent[]>([]);
  const [summaryStats, setSummaryStats] = useState<SummaryStats | null>(null);
  const [overviewData, setOverviewData] = useState<PriceCandle[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Chart Controls State
  const [volumeRatio, setVolumeRatio] = useState(0.2);
  const [showEventMarkers, setShowEventMarkers] = useState(true);
  
  // Refs for synchronization
  const priceChartRef = useRef<PriceChartRef>(null);
  const attentionChartRef = useRef<AttentionChartRef>(null);

  // Fetch Data
  const loadData = useCallback(async (isUpdate = false) => {
    if (isUpdate) setUpdating(true);
    else setLoading(true);
    setError(null);

    try {
      // 1. Critical Data
      const { summary, price } = await dashboardService.fetchCriticalData(symbol, timeframe);
      
      setSummaryStats(summary);
      setPriceData(price);
      
      if (!isUpdate) setLoading(false);

      // 2. Secondary Data
      const startDate = price[0]?.datetime;
      const { attention, news, events } = await dashboardService.fetchSecondaryData(symbol, startDate);

      setAttentionData(attention);
      setNews(news);
      setEvents(events);

      // 3. Background Data
      const overview = await dashboardService.fetchBackgroundData(symbol);
      setOverviewData(overview);

    } catch (error) {
      console.error("Failed to load dashboard data", error);
      setError(error instanceof Error ? error.message : 'Failed to load data');
    } finally {
      setLoading(false);
      setUpdating(false);
    }
  }, [symbol, timeframe]);

  // Initial Load
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handlers
  const handleCrosshairMove = useCallback((time: Time | null) => {
    priceChartRef.current?.setCrosshair(time);
    attentionChartRef.current?.setCrosshair(time);
  }, []);

  // Calculate overview days
  const overviewDays = useMemo(() => {
    if (!overviewData.length) return 0;
    const start = new Date(overviewData[0].timestamp);
    const end = new Date(overviewData[overviewData.length - 1].timestamp);
    const diffTime = Math.abs(end.getTime() - start.getTime());
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
  }, [overviewData]);

  if (loading && !priceData.length && !attentionData.length) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            <p className="text-muted-foreground">Loading {symbol} data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 space-y-4">
        <div className="text-destructive text-lg font-semibold">Error Loading Data</div>
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={() => loadData()} variant="outline">Retry</Button>
      </div>
    );
  }

  const stats = summaryStats || {
    current_price: priceData[priceData.length - 1]?.close || 0,
    price_change_24h: 0,
    price_change_24h_abs: 0,
    volume_24h: priceData[priceData.length - 1]?.volume || 0,
    current_attention: 0,
    avg_attention_7d: 0,
    volatility_30d: 0,
    news_count_today: 0
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Section 1: Top Summary */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <SummaryCard
            symbol={`${symbol}/USDT`}
            price={stats.current_price}
            priceChange={stats.price_change_24h}
            priceChangeAbs={stats.price_change_24h_abs}
            volume24h={stats.volume_24h}
            attention={stats.current_attention}
            selectedSymbol={symbol}
            availableSymbols={availableSymbols}
            onSymbolChange={onSymbolChange}
            onRefresh={() => loadData(true)}
            updating={updating}
            updateCountdown={0}
            enableRealtimePrice={true}
          />
        </div>

        <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard title="News Today" value={stats.news_count_today} decimals={0} />
          <StatCard title="Avg Attention (7d)" value={stats.avg_attention_7d} suffix="/100" />
          <StatCard title="30d Volatility" value={stats.volatility_30d} suffix="%" />
          <StatCard title="24h Change" value={stats.price_change_24h} change={stats.price_change_24h} suffix="%" />
        </div>
      </section>

      {/* Section 2: Middle Panels */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card rounded-lg border p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-primary" />
            Price Overview {overviewDays > 0 && <span className="text-sm font-normal text-muted-foreground">({overviewDays} 天)</span>}
          </h2>
          <PriceOverview priceData={overviewData} height={192} />
        </div>
        <NewsList news={news} maxItems={5} title={`${symbol} RECENT NEWS`} />
      </section>

      {/* Section 3: Main Price Action Chart */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Price Action</h2>
          <div className="flex gap-2">
            {(['15M', '1H', '4H', '1D'] as Timeframe[]).map((tf) => (
              <Button key={tf} variant={timeframe === tf ? 'default' : 'outline'} size="sm" onClick={() => setTimeframe(tf)}>
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
            events={events}
            onCrosshairMove={handleCrosshairMove}
            volumeRatio={volumeRatio}
            onVolumeRatioChange={setVolumeRatio}
            showEventMarkers={showEventMarkers}
            onShowEventMarkersChange={setShowEventMarkers}
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
            onCrosshairMove={handleCrosshairMove}
          />
        </div>
      </section>

      {/* Section 5: Attention Events & Backtest */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Suspense fallback={<div className="h-[200px] bg-muted/50 rounded animate-pulse" />}>
          <AttentionEvents events={events} />
        </Suspense>
        <Suspense fallback={<div className="h-[200px] bg-muted/50 rounded animate-pulse" />}>
          <BacktestPanel />
        </Suspense>
      </section>
      
      {/* Section 6: Attention Regime Analysis */}
      <section>
        <Suspense fallback={<div className="h-[300px] bg-muted/50 rounded animate-pulse" />}>
          <AttentionRegimePanel defaultSymbols={[symbol]} />
        </Suspense>
      </section>
    </div>
  )
}
