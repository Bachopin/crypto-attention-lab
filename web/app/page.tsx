'use client'

import { useState, useEffect, lazy, Suspense, useCallback } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Activity, LayoutGrid, TrendingUp, Newspaper, Settings, Network, BarChart3 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import DashboardTab from '@/components/tabs/DashboardTab'
import { fetchSymbols } from '@/lib/api'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { SettingsProvider } from '@/components/SettingsProvider'
import { TabDataProvider } from '@/components/TabDataProvider'

// Lazy load other tabs
const MarketOverviewTab = lazy(() => import('@/components/tabs/MarketOverviewTab'))
const NewsTab = lazy(() => import('@/components/tabs/NewsTab'))
const SettingsTab = lazy(() => import('@/components/tabs/SettingsTab'))
const ScenarioTab = lazy(() => import('@/components/tabs/ScenarioTab'))
const BacktestTab = lazy(() => import('@/components/tabs/BacktestTab'))

function TabLoading() {
  return (
    <div className="space-y-4 fade-in">
      <div className="h-8 bg-gradient-to-r from-muted/50 via-muted/30 to-muted/50 rounded-lg animate-pulse" />
      <div className="h-[300px] bg-gradient-to-br from-muted/50 via-muted/30 to-muted/50 rounded-lg animate-pulse" />
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-24 bg-gradient-to-br from-muted/50 via-muted/30 to-muted/50 rounded-lg animate-pulse" style={{ animationDelay: `${i * 0.1}s` }} />
        ))}
      </div>
    </div>
  )
}

function FullPageLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-muted/20">
      <div className="flex flex-col items-center gap-6">
        <div className="relative">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-primary/20 border-t-primary"></div>
          <div className="absolute inset-0 animate-ping rounded-full h-16 w-16 border-2 border-primary/30"></div>
        </div>
        <div className="text-center space-y-2">
          <p className="text-lg font-semibold gradient-text">Crypto Attention Lab</p>
          <p className="text-sm text-muted-foreground animate-pulse">Loading...</p>
        </div>
      </div>
    </div>
  )
}

export default function Page() {
  return (
    <SettingsProvider>
      <TabDataProvider>
        <Suspense fallback={<FullPageLoading />}>
          <Home />
        </Suspense>
      </TabDataProvider>
    </SettingsProvider>
  )
}

function Home() {
  const searchParams = useSearchParams()
  const [selectedSymbol, setSelectedSymbol] = useState<string>('ZEC')
  const [availableSymbols, setAvailableSymbols] = useState<string[]>(['ZEC', 'BTC', 'ETH', 'SOL'])
  const [activeTab, setActiveTab] = useState('overview')
  const [mounted, setMounted] = useState(false)

  // Only sync with searchParams after mount to avoid hydration mismatch
  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!mounted) return
    const tab = searchParams.get('tab')
    if (tab && tab !== activeTab) {
      setActiveTab(tab)
    }
  }, [searchParams, mounted, activeTab])

  const refreshSymbols = useCallback(async () => {
    try {
      const data = await fetchSymbols()
      if (data.symbols && data.symbols.length > 0) {
        setAvailableSymbols(data.symbols)
      }
    } catch (err) {
      console.error('Failed to fetch symbols:', err)
      // Optional: Show toast notification here
    }
  }, [])

  // Fetch available symbols on mount
  useEffect(() => {
    refreshSymbols()
  }, [refreshSymbols])

  // Don't render main content until mounted to avoid hydration issues
  if (!mounted) {
    return <FullPageLoading />
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      {/* Header */}
      <header className="border-b border-border/50 bg-card/80 backdrop-blur-md sticky top-0 z-50 shadow-sm">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3 group">
              <div className="relative">
                <Activity className="w-6 h-6 text-primary transition-transform duration-300 group-hover:scale-110 group-hover:rotate-12" />
                <div className="absolute inset-0 bg-primary/20 rounded-full blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
              </div>
              <h1 className="text-xl font-semibold text-foreground/95 tracking-tight transition-colors group-hover:text-foreground">
                Crypto Attention Lab
              </h1>
            </div>
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-auto">
              <TabsList className="bg-muted/50 backdrop-blur-sm border border-border/50">
                <TabsTrigger value="overview" className="gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary transition-all">
                  <LayoutGrid className="w-4 h-4" />
                  市场概况
                </TabsTrigger>
                <TabsTrigger value="dashboard" className="gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary transition-all">
                  <TrendingUp className="w-4 h-4" />
                  代币看板
                </TabsTrigger>
                <TabsTrigger value="scenario" className="gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary transition-all">
                  <Activity className="w-4 h-4" />
                  情景分析
                </TabsTrigger>
                <TabsTrigger value="backtest" className="gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary transition-all">
                  <BarChart3 className="w-4 h-4" />
                  历史回测
                </TabsTrigger>
                <TabsTrigger value="news" className="gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary transition-all">
                  <Newspaper className="w-4 h-4" />
                  新闻概览
                </TabsTrigger>
                <TabsTrigger value="settings" className="gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary transition-all">
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
          
          <TabsContent value="overview" className="mt-0 space-y-6 fade-in" forceMount style={{ display: activeTab === 'overview' ? 'block' : 'none' }}>
            <ErrorBoundary name="overview">
              <Suspense fallback={<TabLoading />}>
                <MarketOverviewTab />
              </Suspense>
            </ErrorBoundary>
          </TabsContent>

          <TabsContent value="dashboard" className="mt-0 space-y-6 fade-in" forceMount style={{ display: activeTab === 'dashboard' ? 'block' : 'none' }}>
             <ErrorBoundary name="dashboard">
               <DashboardTab 
                  symbol={selectedSymbol} 
                  availableSymbols={availableSymbols}
                  onSymbolChange={setSelectedSymbol}
               />
             </ErrorBoundary>
          </TabsContent>

          <TabsContent value="scenario" className="mt-0 space-y-6 fade-in" forceMount style={{ display: activeTab === 'scenario' ? 'block' : 'none' }}>
            <ErrorBoundary name="scenario">
              <Suspense fallback={<TabLoading />}>
                <ScenarioTab defaultSymbol={selectedSymbol} />
              </Suspense>
            </ErrorBoundary>
          </TabsContent>

          <TabsContent value="backtest" className="mt-0 space-y-6 fade-in" forceMount style={{ display: activeTab === 'backtest' ? 'block' : 'none' }}>
            <ErrorBoundary name="backtest">
              <Suspense fallback={<TabLoading />}>
                <BacktestTab />
              </Suspense>
            </ErrorBoundary>
          </TabsContent>

          <TabsContent value="news" className="mt-0 space-y-6 fade-in" forceMount style={{ display: activeTab === 'news' ? 'block' : 'none' }}>
            <ErrorBoundary name="news">
              <Suspense fallback={<TabLoading />}>
                <NewsTab news={[]} />
              </Suspense>
            </ErrorBoundary>
          </TabsContent>

          <TabsContent value="settings" className="mt-0 space-y-6 fade-in" forceMount style={{ display: activeTab === 'settings' ? 'block' : 'none' }}>
            <ErrorBoundary name="settings">
              <Suspense fallback={<TabLoading />}>
                <SettingsTab onUpdate={refreshSymbols} />
              </Suspense>
            </ErrorBoundary>
          </TabsContent>
        </Tabs>
      </main>

      <footer className="border-t border-border/50 mt-12 py-6 bg-card/30 backdrop-blur-sm">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p className="fade-in">Crypto Attention Lab - Analyzing the relationship between news attention and price movements</p>
        </div>
      </footer>
    </div>
  )
}
