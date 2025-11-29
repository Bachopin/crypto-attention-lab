'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import PriceChart, { PriceChartRef } from '@/components/PriceChart'
import AttentionChart, { AttentionChartRef } from '@/components/AttentionChart'
import AttentionEvents from '@/components/AttentionEvents'
import BacktestPanel from '@/components/BacktestPanel'
import AttentionRegimePanel from '@/components/AttentionRegimePanel'
import DashboardTab from '@/components/tabs/DashboardTab'
import MarketOverviewTab from '@/components/tabs/MarketOverviewTab'
import NewsTab from '@/components/tabs/NewsTab'
import SettingsTab from '@/components/tabs/SettingsTab'
import {
  fetchPrice,
  fetchAttention,
  fetchNews,
  fetchSummaryStats,
  fetchAttentionEvents,
  type Timeframe,
  type PriceCandle,
  type AttentionData,
  type NewsItem,
  type SummaryStats,
} from '@/lib/api'
import { Activity, TrendingUp, Newspaper, Settings, Network, LayoutGrid } from 'lucide-react'
import { Range, Time } from 'lightweight-charts'
import Link from 'next/link'

export default function Home() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>('ZEC')
  const [availableSymbols, setAvailableSymbols] = useState<string[]>(['ZEC', 'BTC', 'ETH', 'SOL'])
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>('1D')
  const [priceData, setPriceData] = useState<PriceCandle[]>([])
  const [overviewPriceData, setOverviewPriceData] = useState<PriceCandle[]>([])
  const [attentionData, setAttentionData] = useState<AttentionData[]>([])
  const [newsData, setNewsData] = useState<NewsItem[]>([])
  const [assetNewsData, setAssetNewsData] = useState<NewsItem[]>([])
  const [events, setEvents] = useState<import('@/lib/api').AttentionEvent[]>([])
  const [summaryStats, setSummaryStats] = useState<SummaryStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState(false)
  const [updateCountdown, setUpdateCountdown] = useState(0)
  const [activeTab, setActiveTab] = useState('overview')

  // Chart settings persistence
  const [volumeRatio, setVolumeRatio] = useState(0.2)
  const [showEventMarkers, setShowEventMarkers] = useState(true)

  // Refs for chart synchronization
  const priceChartRef = useRef<PriceChartRef>(null)
  const attentionChartRef = useRef<AttentionChartRef>(null)

  const timeframes: Timeframe[] = ['1D', '4H', '1H', '15M']

  // Fetch available symbols on mount
  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/symbols`)
      .then(res => res.json())
      .then(data => {
        if (data.symbols && data.symbols.length > 0) {
          setAvailableSymbols(data.symbols)
        }
      })
      .catch(err => console.error('Failed to fetch symbols:', err))
  }, [])

  // Handle visible range changes from price chart
  const handlePriceRangeChange = useCallback((range: Range<Time> | null) => {
    if (range && attentionChartRef.current) {
      attentionChartRef.current.setVisibleRange(range)
    }
  }, [])

  // Handle visible range changes from attention chart
  const handleAttentionRangeChange = useCallback((range: Range<Time> | null) => {
    if (range && priceChartRef.current) {
      priceChartRef.current.setVisibleRange(range)
    }
  }, [])

  // Handle crosshair synchronization
  const handleCrosshairMove = useCallback((time: Time | null) => {
    priceChartRef.current?.setCrosshair(time)
    attentionChartRef.current?.setCrosshair(time)
  }, [])

  // Data loader with stable reference
  const loadData = useCallback(async (symbol: string, timeframe: Timeframe, showLoading = true) => {
    if (showLoading) {
      setLoading(true)
    }
    setError(null)
    try {
      const [price, overviewPrice, attention, news, assetNews, summary, attEvents] = await Promise.all([
        fetchPrice({ symbol: `${symbol}USDT`, timeframe: timeframe }),
        fetchPrice({ symbol: `${symbol}USDT`, timeframe: '1D', limit: 90 }),
        fetchAttention({ symbol: symbol, granularity: '1d' }),
        fetchNews({ symbol: 'ALL', limit: 100 }),
        fetchNews({ symbol: symbol }),
        fetchSummaryStats(symbol),
        fetchAttentionEvents({ symbol: symbol, lookback_days: 30, min_quantile: 0.8 }),
      ])

      setPriceData(price)
      setOverviewPriceData(overviewPrice)
      setAttentionData(attention)
      setNewsData(news)
      setAssetNewsData(assetNews)
      setSummaryStats(summary)
      setEvents(attEvents)
    } catch (error) {
      console.error('Failed to load data:', error)
      setError(error instanceof Error ? error.message : 'Failed to load data from backend')
    } finally {
      if (showLoading) {
        setLoading(false)
      }
    }
  }, [])

  // 仅更新价格数据（用于时间周期切换，无闪烁）
  const updatePriceOnly = useCallback(async (symbol: string, timeframe: Timeframe) => {
    try {
      const price = await fetchPrice({ symbol: `${symbol}USDT`, timeframe: timeframe })
      setPriceData(price)
    } catch (error) {
      console.error('Failed to update price data:', error)
    }
  }, [])

  // Load data on symbol change (with loading)
  useEffect(() => {
    loadData(selectedSymbol, selectedTimeframe, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSymbol, loadData])

  // Update price only on timeframe change (without loading)
  useEffect(() => {
    updatePriceOnly(selectedSymbol, selectedTimeframe)
  }, [selectedTimeframe, updatePriceOnly, selectedSymbol])

  // 静默加载数据（不显示 loading 动画）
  const loadDataSilently = useCallback(async () => {
    try {
      const [price, overviewPrice, attention, news, assetNews, summary, attEvents] = await Promise.all([
        fetchPrice({ symbol: `${selectedSymbol}USDT`, timeframe: selectedTimeframe }),
        fetchPrice({ symbol: `${selectedSymbol}USDT`, timeframe: '1D', limit: 90 }),
        fetchAttention({ symbol: selectedSymbol, granularity: '1d' }),
        fetchNews({ symbol: 'ALL', limit: 100 }),
        fetchNews({ symbol: selectedSymbol }),
        fetchSummaryStats(selectedSymbol),
        fetchAttentionEvents({ symbol: selectedSymbol, lookback_days: 30, min_quantile: 0.8 }),
      ])
      if (price.length > 0) setPriceData(price)
      if (overviewPrice.length > 0) setOverviewPriceData(overviewPrice)
      if (attention.length > 0) setAttentionData(attention)
      if (news.length > 0) setNewsData(news)
      if (assetNews.length > 0) setAssetNewsData(assetNews)
      if (summary) setSummaryStats(summary)
      if (attEvents.length >= 0) setEvents(attEvents)
    } catch (err) {
      console.error('[loadDataSilently] Failed:', err)
    }
  }, [selectedTimeframe, selectedSymbol])

  // 刷新当前标的数据
  const refreshCurrentSymbol = useCallback(async () => {
    setUpdating(true)
    setUpdateCountdown(20)
    const countdownInterval = setInterval(() => {
      setUpdateCountdown(prev => {
        if (prev <= 1) {
          clearInterval(countdownInterval)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/update-data`,
        { method: 'POST' }
      )
      clearInterval(countdownInterval)
      if (response.ok) {
        await new Promise(resolve => setTimeout(resolve, 500))
        await loadDataSilently()
      }
    } catch (err) {
      console.error('[refreshCurrentSymbol] Error:', err)
      clearInterval(countdownInterval)
    } finally {
      setUpdating(false)
      setUpdateCountdown(0)
    }
  }, [loadDataSilently])

  // 刷新可选代币列表（用于设置页添加后同步看板）
  const refreshSymbols = useCallback(async () => {
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}/api/symbols`)
      const data = await res.json()
      if (Array.isArray(data.symbols) && data.symbols.length) {
        setAvailableSymbols(data.symbols)
        // 若当前选中代币不在列表中，自动切换到第一个
        if (!data.symbols.includes(selectedSymbol)) {
          setSelectedSymbol(data.symbols[0])
        }
      }
    } catch (err) {
      console.error('[refreshSymbols] Failed:', err)
    }
  }, [selectedSymbol])

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      refreshCurrentSymbol()
    }, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [refreshCurrentSymbol])

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur sticky top-0 z-50">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <Activity className="w-6 h-6 text-primary" />
              <h1 className="text-xl font-bold">Crypto Attention Lab</h1>
            </div>
            {/* 主导航 Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-auto">
              <TabsList>
                <TabsTrigger value="overview" className="gap-2">
                  <LayoutGrid className="w-4 h-4" />
                  市场概况
                </TabsTrigger>
                <TabsTrigger value="dashboard" className="gap-2">
                  <TrendingUp className="w-4 h-4" />
                  代币看板
                </TabsTrigger>
                <TabsTrigger value="news" className="gap-2">
                  <Newspaper className="w-4 h-4" />
                  新闻概览
                </TabsTrigger>
                <TabsTrigger value="settings" className="gap-2">
                  <Settings className="w-4 h-4" />
                  系统设置
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/node-influence">
              <Button variant="outline" size="sm" className="gap-2">
                <Network className="w-4 h-4" />
                节点因子
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6 space-y-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          {/* 市场概况 - 独立加载，不依赖主页面数据 */}
          <TabsContent value="overview" className="mt-0 space-y-6">
            <MarketOverviewTab />
          </TabsContent>

          {/* 代币看板 - 需要等待数据加载 */}
          <TabsContent value="dashboard" className="mt-0 space-y-6">
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
                  <Button onClick={() => loadData(selectedSymbol, selectedTimeframe, true)}>Retry</Button>
                </div>
              </div>
            )}

            {/* Fallback State */}
            {!loading && !error && !summaryStats && (
              <div className="flex items-center justify-center h-64">
                <div className="text-center max-w-md text-muted-foreground">
                  <div className="text-5xl mb-4">ℹ️</div>
                  <h2 className="text-xl font-semibold mb-2">No data available</h2>
                  <p className="text-sm">Try refreshing data or check backend.</p>
                  <div className="mt-4"><Button onClick={() => loadData(selectedSymbol, selectedTimeframe, true)}>Reload</Button></div>
                </div>
              </div>
            )}

            {!loading && summaryStats && (
              <>
                <DashboardTab
                  selectedSymbol={selectedSymbol}
                  availableSymbols={availableSymbols}
                  summaryStats={summaryStats}
                  assetNewsData={assetNewsData}
                  priceData={priceData}
                  overviewPriceData={overviewPriceData}
                  attentionData={attentionData}
                  events={events}
                  selectedTimeframe={selectedTimeframe}
                  timeframes={timeframes}
                  onTimeframeChange={setSelectedTimeframe}
                  volumeRatio={volumeRatio}
                  onVolumeRatioChange={setVolumeRatio}
                  showEventMarkers={showEventMarkers}
                  onShowEventMarkersChange={setShowEventMarkers}
                  onSymbolChange={setSelectedSymbol}
                  onRefresh={refreshCurrentSymbol}
                  updating={updating}
                  updateCountdown={updateCountdown}
                  priceChartRef={priceChartRef}
                  attentionChartRef={attentionChartRef}
                  onPriceRangeChange={handlePriceRangeChange}
                  onAttentionRangeChange={handleAttentionRangeChange}
                  onCrosshairMove={handleCrosshairMove}
                />

                {/* Attention Events & Backtest */}
                <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <AttentionEvents events={events} />
                  <BacktestPanel />
                </section>
                
                <section>
                  <AttentionRegimePanel />
                </section>
              </>
            )}
          </TabsContent>

          {/* 新闻概览 */}
          <TabsContent value="news" className="mt-0 space-y-6">
            <NewsTab news={newsData} />
          </TabsContent>

          {/* 系统设置 */}
          <TabsContent value="settings" className="mt-0 space-y-6">
            <SettingsTab onUpdate={() => { loadDataSilently(); refreshSymbols(); }} />
          </TabsContent>
        </Tabs>
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
