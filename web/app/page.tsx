'use client'

import { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import PriceChart, { PriceChartRef } from '@/components/PriceChart'
import AttentionChart, { AttentionChartRef } from '@/components/AttentionChart'
import DashboardTab from '@/components/tabs/DashboardTab'
import {
  fetchPrice,
  fetchAttention,
  fetchNews,
  fetchSummaryStats,
  fetchAttentionEvents,
  buildApiUrl,
  getApiBaseUrl,
  type Timeframe,
  type PriceCandle,
  type AttentionData,
  type NewsItem,
  type SummaryStats,
} from '@/lib/api'
import { Activity, TrendingUp, Newspaper, Settings, Network, LayoutGrid } from 'lucide-react'
import { Range, Time } from 'lightweight-charts'
import Link from 'next/link'

import { SettingsProvider, useSettings } from '@/components/SettingsProvider'
import { TabDataProvider } from '@/components/TabDataProvider'

// 懒加载非首屏组件
const MarketOverviewTab = lazy(() => import('@/components/tabs/MarketOverviewTab'))
const NewsTab = lazy(() => import('@/components/tabs/NewsTab'))
const SettingsTab = lazy(() => import('@/components/tabs/SettingsTab'))
const ScenarioTab = lazy(() => import('@/components/tabs/ScenarioTab'))
const BacktestPanel = lazy(() => import('@/components/BacktestPanel'))
const AttentionRegimePanel = lazy(() => import('@/components/AttentionRegimePanel'))
const AttentionEvents = lazy(() => import('@/components/AttentionEvents'))

// 加载占位符
function TabLoading() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 bg-muted/50 rounded w-1/4" />
      <div className="h-[300px] bg-muted/50 rounded" />
    </div>
  )
}

export default function Page() {
  return (
    <SettingsProvider>
      <TabDataProvider>
        <Home />
      </TabDataProvider>
    </SettingsProvider>
  )
}

function Home() {
  const { settings } = useSettings()
  const [selectedSymbol, setSelectedSymbol] = useState<string>('ZEC')
  const [availableSymbols, setAvailableSymbols] = useState<string[]>(['ZEC', 'BTC', 'ETH', 'SOL'])
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>(settings.defaultTimeframe)
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
    fetch(buildApiUrl('/api/symbols'))
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

  // Data loader with stable reference - 渐进式加载优化
  const loadData = useCallback(async (symbol: string, timeframe: Timeframe, showLoading = true) => {
    if (showLoading) {
      setLoading(true)
    }
    setError(null)
    
    try {
      // 第一阶段：优先加载核心数据（价格 + 概览），快速显示主界面
      const [price, overviewPrice] = await Promise.all([
        fetchPrice({ symbol: `${symbol}USDT`, timeframe: timeframe }).catch(() => []),
        fetchPrice({ symbol: `${symbol}USDT`, timeframe: '1D' }).catch(() => []),
      ])
      
      // 检查是否有数据
      if (price.length === 0 && overviewPrice.length === 0) {
        setError(`代币 ${symbol} 暂无数据。请等待数据同步完成，或检查该代币是否在 Binance 上存在。`)
        if (showLoading) {
          setLoading(false)
        }
        return
      }
      
      setPriceData(price)
      setOverviewPriceData(overviewPrice)
      
      // 立即结束 loading 状态，让用户看到图表
      if (showLoading) {
        setLoading(false)
      }
      
      // 第二阶段：后台加载其他数据（注意力、新闻、事件等）- 容错处理
      const [attention, news, assetNews, summary, attEvents] = await Promise.all([
        fetchAttention({ symbol: symbol, granularity: '1d' }).catch(() => []),
        fetchNews({ symbol: 'ALL', limit: 100 }).catch(() => []),
        fetchNews({ symbol: symbol }).catch(() => []),
        fetchSummaryStats(symbol).catch(() => null),
        fetchAttentionEvents({ symbol: symbol, lookback_days: settings.defaultWindowDays, min_quantile: 0.9 }).catch(() => []),
      ])
      
      setAttentionData(attention)
      setNewsData(news)
      setAssetNewsData(assetNews)
      if (summary) setSummaryStats(summary)
      setEvents(attEvents)
    } catch (error) {
      console.error('Failed to load data:', error)
      setError(error instanceof Error ? error.message : 'Failed to load data from backend')
      if (showLoading) {
        setLoading(false)
      }
    }
  }, [settings.defaultWindowDays])

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
        fetchPrice({ symbol: `${selectedSymbol}USDT`, timeframe: '1D' }), // 获取所有日线数据
        fetchAttention({ symbol: selectedSymbol, granularity: '1d' }),
        fetchNews({ symbol: 'ALL', limit: 100 }),
        fetchNews({ symbol: selectedSymbol }),
        fetchSummaryStats(selectedSymbol),
        fetchAttentionEvents({ symbol: selectedSymbol, lookback_days: settings.defaultWindowDays, min_quantile: 0.9 }),
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
  }, [selectedTimeframe, selectedSymbol, settings.defaultWindowDays])

  // Countdown effect
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (updating && updateCountdown > 0) {
      interval = setInterval(() => {
        setUpdateCountdown(prev => (prev > 0 ? prev - 1 : 0))
      }, 1000)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [updating, updateCountdown])

  // 刷新当前标的数据（调用新的 refresh-symbol API）
  const refreshCurrentSymbol = useCallback(async () => {
    setUpdating(true)
    setUpdateCountdown(30)
    
    try {
      // 调用针对单个 symbol 的刷新接口，默认检查数据完整性
      const response = await fetch(
        buildApiUrl(`/api/refresh-symbol?symbol=${selectedSymbol}`),
        { method: 'POST' }
      )
      
      if (response.ok) {
        const result = await response.json()
        console.log('[refreshCurrentSymbol] Result:', result)
        // 等待一小段时间确保数据已写入
        await new Promise(resolve => setTimeout(resolve, 300))
        // 清除缓存并重新加载数据
        const { clearApiCache } = await import('@/lib/api')
        clearApiCache()
        await loadDataSilently()
      } else {
        console.error('[refreshCurrentSymbol] API error:', await response.text())
      }
    } catch (err) {
      console.error('[refreshCurrentSymbol] Error:', err)
    } finally {
      setUpdating(false)
      setUpdateCountdown(0)
    }
  }, [loadDataSilently, selectedSymbol])

  // 刷新可选代币列表（用于设置页添加后同步看板）
  const refreshSymbols = useCallback(async () => {
    try {
      const res = await fetch(buildApiUrl('/api/symbols'))
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
                <TabsTrigger value="scenario" className="gap-2">
                  <Activity className="w-4 h-4" />
                  情景分析
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
          {/* 市场概况 - 懒加载 */}
          <TabsContent value="overview" className="mt-0 space-y-6">
            <Suspense fallback={<TabLoading />}>
              <MarketOverviewTab />
            </Suspense>
          </TabsContent>

          {/* 代币看板 - 需要等待数据加载 */}
          <TabsContent value="dashboard" className="mt-0 space-y-6">
            {/* Loading State - 骨架屏 */}
            {loading && (
              <div className="space-y-6 animate-pulse">
                {/* Header skeleton */}
                <div className="flex gap-4">
                  <div className="bg-muted/50 rounded-lg h-24 w-1/3" />
                  <div className="bg-muted/50 rounded-lg h-24 w-1/3" />
                  <div className="bg-muted/50 rounded-lg h-24 w-1/3" />
                </div>
                {/* Chart skeleton */}
                <div className="bg-muted/50 rounded-lg h-[400px]" />
                {/* Bottom section skeleton */}
                <div className="flex gap-4">
                  <div className="bg-muted/50 rounded-lg h-[200px] w-2/3" />
                  <div className="bg-muted/50 rounded-lg h-[200px] w-1/3" />
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
                    {`Make sure the FastAPI backend is reachable via ${getApiBaseUrl() || 'the Next.js proxy (/api → backend)'}`}
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

                {/* Attention Events & Backtest - 懒加载 */}
                <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Suspense fallback={<div className="h-[200px] bg-muted/50 rounded animate-pulse" />}>
                    <AttentionEvents events={events} />
                  </Suspense>
                  <Suspense fallback={<div className="h-[200px] bg-muted/50 rounded animate-pulse" />}>
                    <BacktestPanel />
                  </Suspense>
                </section>
                
                <section>
                  <Suspense fallback={<div className="h-[300px] bg-muted/50 rounded animate-pulse" />}>
                    <AttentionRegimePanel />
                  </Suspense>
                </section>
              </>
            )}
          </TabsContent>

          {/* 情景分析 - 懒加载 */}
          <TabsContent value="scenario" className="mt-0 space-y-6">
            <Suspense fallback={<TabLoading />}>
              <ScenarioTab defaultSymbol={selectedSymbol} />
            </Suspense>
          </TabsContent>

          {/* 新闻概览 - 懒加载 */}
          <TabsContent value="news" className="mt-0 space-y-6">
            <Suspense fallback={<TabLoading />}>
              <NewsTab news={newsData} />
            </Suspense>
          </TabsContent>

          {/* 系统设置 - 懒加载 */}
          <TabsContent value="settings" className="mt-0 space-y-6">
            <Suspense fallback={<TabLoading />}>
              <SettingsTab onUpdate={() => { loadDataSilently(); refreshSymbols(); }} />
            </Suspense>
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
