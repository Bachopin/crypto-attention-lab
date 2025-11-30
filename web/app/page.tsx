'use client'

import { useState, useEffect, lazy, Suspense } from 'react'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import DashboardTab from '@/components/tabs/DashboardTab'
import { buildApiUrl } from '@/lib/api'
import { Activity, TrendingUp, Newspaper, Settings, Network, LayoutGrid } from 'lucide-react'
import Link from 'next/link'
import { SettingsProvider } from '@/components/SettingsProvider'
import { TabDataProvider } from '@/components/TabDataProvider'

// Lazy load other tabs
const MarketOverviewTab = lazy(() => import('@/components/tabs/MarketOverviewTab'))
const NewsTab = lazy(() => import('@/components/tabs/NewsTab'))
const SettingsTab = lazy(() => import('@/components/tabs/SettingsTab'))
const ScenarioTab = lazy(() => import('@/components/tabs/ScenarioTab'))

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
  const [selectedSymbol, setSelectedSymbol] = useState<string>('ZEC')
  const [availableSymbols, setAvailableSymbols] = useState<string[]>(['ZEC', 'BTC', 'ETH', 'SOL'])
  const [activeTab, setActiveTab] = useState('overview')

  const refreshSymbols = () => {
    fetch(buildApiUrl('/api/symbols'))
      .then(res => res.json())
      .then(data => {
        if (data.symbols && data.symbols.length > 0) {
          setAvailableSymbols(data.symbols)
        }
      })
      .catch(err => console.error('Failed to fetch symbols:', err))
  }

  // Fetch available symbols on mount
  useEffect(() => {
    refreshSymbols()
  }, [])

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
          
          <TabsContent value="overview" className="mt-0 space-y-6" forceMount style={{ display: activeTab === 'overview' ? 'block' : 'none' }}>
            <Suspense fallback={<TabLoading />}>
              <MarketOverviewTab />
            </Suspense>
          </TabsContent>

          <TabsContent value="dashboard" className="mt-0 space-y-6" forceMount style={{ display: activeTab === 'dashboard' ? 'block' : 'none' }}>
             <DashboardTab 
                symbol={selectedSymbol} 
                availableSymbols={availableSymbols}
                onSymbolChange={setSelectedSymbol}
             />
          </TabsContent>

          <TabsContent value="scenario" className="mt-0 space-y-6" forceMount style={{ display: activeTab === 'scenario' ? 'block' : 'none' }}>
            <Suspense fallback={<TabLoading />}>
              <ScenarioTab defaultSymbol={selectedSymbol} />
            </Suspense>
          </TabsContent>

          <TabsContent value="news" className="mt-0 space-y-6" forceMount style={{ display: activeTab === 'news' ? 'block' : 'none' }}>
            <Suspense fallback={<TabLoading />}>
              <NewsTab news={[]} />
            </Suspense>
          </TabsContent>

          <TabsContent value="settings" className="mt-0 space-y-6" forceMount style={{ display: activeTab === 'settings' ? 'block' : 'none' }}>
            <Suspense fallback={<TabLoading />}>
              <SettingsTab onUpdate={refreshSymbols} />
            </Suspense>
          </TabsContent>
        </Tabs>
      </main>

      <footer className="border-t border-border mt-12 py-6">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>Crypto Attention Lab - Analyzing the relationship between news attention and price movements</p>
        </div>
      </footer>
    </div>
  )
}
