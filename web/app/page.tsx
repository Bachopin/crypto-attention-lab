'use client'

import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { StatCard, SummaryCard } from '@/components/StatCards'
import PriceChart, { PriceChartRef } from '@/components/PriceChart'
import AttentionChart, { AttentionChartRef } from '@/components/AttentionChart'
import PriceOverview from '@/components/PriceOverview'
import NewsList from '@/components/NewsList'
import {
  fetchPrice,
  fetchAttention,
  fetchNews,
  fetchSummaryStats,
  type Timeframe,
  type PriceCandle,
  type AttentionData,
  type NewsItem,
  type SummaryStats,
} from '@/lib/api'
import { Activity, TrendingUp, BarChart3 } from 'lucide-react'
import { Range, Time } from 'lightweight-charts'

export default function Home() {
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>('1D')
  const [priceData, setPriceData] = useState<PriceCandle[]>([])
  const [attentionData, setAttentionData] = useState<AttentionData[]>([])
  const [newsData, setNewsData] = useState<NewsItem[]>([])
  const [summaryStats, setSummaryStats] = useState<SummaryStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState(false)

  // Refs for chart synchronization
  const priceChartRef = useRef<PriceChartRef>(null)
  const attentionChartRef = useRef<AttentionChartRef>(null)

  const timeframes: Timeframe[] = ['1D', '4H', '1H', '15M', '5M', '1M']

  // Handle visible range changes from price chart
  const handlePriceRangeChange = (range: Range<Time> | null) => {
    if (range && attentionChartRef.current) {
      attentionChartRef.current.setVisibleRange(range)
    }
  }

  // Handle visible range changes from attention chart
  const handleAttentionRangeChange = (range: Range<Time> | null) => {
    if (range && priceChartRef.current) {
      priceChartRef.current.setVisibleRange(range)
    }
  }

  // Load data
  useEffect(() => {
    loadData()
  }, [selectedTimeframe])

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      console.log('[Auto-refresh] Triggering background data update...')
      updateRemoteData()
    }, 5 * 60 * 1000)

    return () => clearInterval(interval)
  }, [])

  async function updateRemoteData() {
    setUpdating(true)
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/update-data`,
        { method: 'POST' }
      )
      if (response.ok) {
        console.log('[updateRemoteData] Server data refreshed, reloading...')
        await loadData()
      } else {
        console.warn('[updateRemoteData] Failed:', response.status)
      }
    } catch (err) {
      console.error('[updateRemoteData] Error:', err)
    } finally {
      setUpdating(false)
    }
  }

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      console.log('[loadData] Starting data fetch...');
      
      const [price, attention, news, summary] = await Promise.all([
        fetchPrice({ symbol: 'ZECUSDT', timeframe: selectedTimeframe }),
        fetchAttention({ symbol: 'ZEC', granularity: '1d' }),
        fetchNews({ symbol: 'ZEC' }),
        fetchSummaryStats('ZEC'),
      ])

      console.log('[loadData] Fetched:', {
        price: price.length,
        attention: attention.length,
        news: news.length,
        summary
      });

      setPriceData(price)
      setAttentionData(attention)
      setNewsData(news)
      setSummaryStats(summary)
      
      console.log('[loadData] State updated successfully');
    } catch (error) {
      console.error('Failed to load data:', error)
      setError(error instanceof Error ? error.message : 'Failed to load data from backend')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-0 z-50">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6 text-primary" />
            <h1 className="text-xl font-bold">Crypto Attention Lab</h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">ZEC Analysis Dashboard</span>
            <Button
              variant="outline"
              size="sm"
              onClick={updateRemoteData}
              disabled={updating}
              className="text-xs"
            >
              {updating ? '更新中...' : '刷新数据'}
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center h-64">
            <div className="flex flex-col items-center gap-4">
              <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
              <p className="text-muted-foreground">Loading market data...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="flex items-center justify-center h-64">
            <div className="text-center max-w-md">
              <div className="text-5xl mb-4">⚠️</div>
              <h2 className="text-xl font-semibold mb-2">Failed to Load Data</h2>
              <p className="text-muted-foreground mb-4">{error}</p>
              <p className="text-sm text-muted-foreground/70 mb-6">
                Make sure the FastAPI backend is running at {process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}
              </p>
              <Button onClick={loadData}>Retry</Button>
            </div>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="flex items-center justify-center h-64">
            <div className="text-center max-w-md">
              <div className="text-5xl mb-4">⚠️</div>
              <h2 className="text-xl font-semibold mb-2">Failed to Load Data</h2>
              <p className="text-muted-foreground mb-4">{error}</p>
              <p className="text-sm text-muted-foreground/70 mb-6">
                Make sure the FastAPI backend is running at {process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}
              </p>
              <Button onClick={loadData}>Retry</Button>
            </div>
          </div>
        )}

        {!loading && summaryStats && (
          <>
            {/* Section 1: Top Summary */}
            <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Main Summary Card */}
              <div className="lg:col-span-1">
                <SummaryCard
                  symbol="ZEC/USDT"
                  price={summaryStats.current_price}
                  priceChange={summaryStats.price_change_24h}
                  priceChangeAbs={summaryStats.price_change_24h_abs}
                  volume24h={summaryStats.volume_24h}
                  attention={summaryStats.current_attention}
                />
              </div>

              {/* Stat Cards Grid */}
              <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                  title="News Today"
                  value={summaryStats.news_count_today}
                  decimals={0}
                />
                <StatCard
                  title="Avg Attention (7d)"
                  value={summaryStats.avg_attention_7d}
                  suffix="/100"
                />
                <StatCard
                  title="30d Volatility"
                  value={summaryStats.volatility_30d}
                  suffix="%"
                />
                <StatCard
                  title="24h Change"
                  value={summaryStats.price_change_24h}
                  change={summaryStats.price_change_24h}
                  suffix="%"
                />
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
                <PriceOverview priceData={priceData} height={192} />
              </div>

              {/* Recent News */}
              <NewsList news={newsData} maxItems={5} />
            </section>

            {/* Section 3: Main Price Action Chart */}
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold">Price Action</h2>
                
                {/* Timeframe Selector */}
                <div className="flex gap-2">
                  {timeframes.map((tf) => (
                    <Button
                      key={tf}
                      variant={selectedTimeframe === tf ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setSelectedTimeframe(tf)}
                    >
                      {tf}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="bg-card rounded-lg border p-4">
                <PriceChart
                  ref={priceChartRef}
                  priceData={priceData}
                  height={600}
                  onVisibleRangeChange={handlePriceRangeChange}
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
                  onVisibleRangeChange={handleAttentionRangeChange}
                />
              </div>
            </section>

            {/* Section 5: Full News List */}
            <section>
              <h2 className="text-xl font-bold mb-4">All News</h2>
              <NewsList news={newsData} maxItems={20} />
            </section>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-12 py-6">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>Crypto Attention Lab - Analyzing the relationship between news attention and price movements</p>
        </div>
      </footer>
    </div>
  )
}
