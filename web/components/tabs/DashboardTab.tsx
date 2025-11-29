"use client"

import React, { useState, useEffect, useMemo, useRef, useCallback, lazy, Suspense } from 'react'
import { Button } from '@/components/ui/button'
import { StatCard, SummaryCard } from '@/components/StatCards'
import PriceChart, { PriceChartRef } from '@/components/PriceChart'
import AttentionChart, { AttentionChartRef } from '@/components/AttentionChart'
import PriceOverview from '@/components/PriceOverview'
import NewsList from '@/components/NewsList'
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
import type { Time } from 'lightweight-charts'

// Lazy load heavy components
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

    try {
      // Fetch in parallel but handle failures gracefully
      const [pData, aData, nData, eData, sData, oData] = await Promise.all([
        fetchPrice({ symbol: `${symbol}USDT`, timeframe }).catch(e => { console.error(e); return []; }),
        fetchAttention({ symbol, granularity: '1d' }).catch(e => { console.error(e); return []; }),
        fetchNews({ symbol }).catch(e => { console.error(e); return []; }),
        fetchAttentionEvents({ symbol }).catch(e => { console.error(e); return []; }),
        fetchSummaryStats(symbol).catch(e => { console.error(e); return null; }),
        // Fetch full history 4H data for overview
        fetchPrice({ symbol: `${symbol}USDT`, timeframe: '4H' }).catch(e => { console.error(e); return []; })
      ]);

      setPriceData(pData);
      setAttentionData(aData);
      setNews(nData);
      setEvents(eData);
      setSummaryStats(sData);
      setOverviewData(oData);
    } catch (error) {
      console.error("Failed to load dashboard data", error);
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
