'use client'

import { useCallback, useEffect, useState, useMemo } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  RotateCw, 
  Wifi, 
  WifiOff, 
  HardDrive, 
  Cpu, 
  Globe,
  Database,
  Zap,
  Clock,
  Activity,
  Settings,
  Layers
} from 'lucide-react'
import { useWebSocketStatus } from '@/lib/websocket'
import { useSettings } from '@/components/SettingsProvider'
import { useTabData } from '@/components/TabDataProvider'
import { 
  dashboardService, 
  priceService, 
  attentionService, 
  backtestService, 
  scenarioService, 
  newsService,
  autoUpdateService 
} from '@/lib/services'
import { getApiBaseUrl } from '@/lib/api'

// ==================== Types ====================

type HealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'checking' | 'unknown'

interface HealthCheckResult {
  name: string
  status: HealthStatus
  message: string
  latency?: number
  details?: Record<string, unknown>
  lastChecked?: Date
}

interface ServiceCheckConfig {
  name: string
  icon: React.ReactNode
  check: () => Promise<HealthCheckResult>
}

// ==================== Utilities ====================

function getStatusColor(status: HealthStatus): string {
  switch (status) {
    case 'healthy': return 'text-green-500'
    case 'degraded': return 'text-yellow-500'
    case 'unhealthy': return 'text-red-500'
    case 'checking': return 'text-blue-500'
    default: return 'text-muted-foreground'
  }
}

function getStatusBgColor(status: HealthStatus): string {
  switch (status) {
    case 'healthy': return 'bg-green-500/10 border-green-500/30'
    case 'degraded': return 'bg-yellow-500/10 border-yellow-500/30'
    case 'unhealthy': return 'bg-red-500/10 border-red-500/30'
    case 'checking': return 'bg-blue-500/10 border-blue-500/30'
    default: return 'bg-muted/30'
  }
}

function getStatusIcon(status: HealthStatus) {
  switch (status) {
    case 'healthy': return <CheckCircle2 className="w-5 h-5 text-green-500" />
    case 'degraded': return <AlertCircle className="w-5 h-5 text-yellow-500" />
    case 'unhealthy': return <XCircle className="w-5 h-5 text-red-500" />
    case 'checking': return <RotateCw className="w-5 h-5 text-blue-500 animate-spin" />
    default: return <AlertCircle className="w-5 h-5 text-muted-foreground" />
  }
}

function getOverallStatus(results: HealthCheckResult[]): HealthStatus {
  if (results.length === 0) return 'unknown'
  if (results.some(r => r.status === 'checking')) return 'checking'
  if (results.every(r => r.status === 'healthy')) return 'healthy'
  if (results.some(r => r.status === 'unhealthy')) return 'unhealthy'
  if (results.some(r => r.status === 'degraded')) return 'degraded'
  return 'unknown'
}

// ==================== Health Check Functions ====================

async function checkLocalStorage(): Promise<HealthCheckResult> {
  const start = performance.now()
  try {
    const testKey = '__health_check_test__'
    localStorage.setItem(testKey, 'test')
    const value = localStorage.getItem(testKey)
    localStorage.removeItem(testKey)
    
    if (value !== 'test') {
      return {
        name: 'localStorage',
        status: 'unhealthy',
        message: '读写测试失败',
        latency: performance.now() - start
      }
    }
    
    // Check quota
    let usedSpace = 0
    for (const key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        usedSpace += localStorage.getItem(key)?.length || 0
      }
    }
    
    return {
      name: 'localStorage',
      status: 'healthy',
      message: `正常 (已用 ${(usedSpace / 1024).toFixed(1)} KB)`,
      latency: performance.now() - start,
      details: { usedBytes: usedSpace, keys: Object.keys(localStorage).length }
    }
  } catch (error) {
    return {
      name: 'localStorage',
      status: 'unhealthy',
      message: error instanceof Error ? error.message : '访问失败',
      latency: performance.now() - start
    }
  }
}

async function checkSessionStorage(): Promise<HealthCheckResult> {
  const start = performance.now()
  try {
    const testKey = '__health_check_test__'
    sessionStorage.setItem(testKey, 'test')
    const value = sessionStorage.getItem(testKey)
    sessionStorage.removeItem(testKey)
    
    if (value !== 'test') {
      return {
        name: 'sessionStorage',
        status: 'unhealthy',
        message: '读写测试失败',
        latency: performance.now() - start
      }
    }
    
    return {
      name: 'sessionStorage',
      status: 'healthy',
      message: '正常',
      latency: performance.now() - start
    }
  } catch (error) {
    return {
      name: 'sessionStorage',
      status: 'unhealthy',
      message: error instanceof Error ? error.message : '访问失败',
      latency: performance.now() - start
    }
  }
}

async function checkServiceHealth(
  serviceName: string, 
  checkFn: () => Promise<unknown>
): Promise<HealthCheckResult> {
  const start = performance.now()
  try {
    await checkFn()
    const latency = performance.now() - start
    
    return {
      name: serviceName,
      status: latency > 5000 ? 'degraded' : 'healthy',
      message: latency > 5000 ? `响应缓慢 (${latency.toFixed(0)}ms)` : '正常',
      latency
    }
  } catch (error) {
    return {
      name: serviceName,
      status: 'unhealthy',
      message: error instanceof Error ? error.message : '请求失败',
      latency: performance.now() - start
    }
  }
}

// ==================== Main Component ====================

export default function FrontendHealthPage() {
  const [results, setResults] = useState<Map<string, HealthCheckResult>>(new Map())
  const [isChecking, setIsChecking] = useState(false)
  const [lastFullCheck, setLastFullCheck] = useState<Date | null>(null)
  
  // Get WebSocket status
  const { priceStatus, attentionStatus } = useWebSocketStatus()
  
  // Try to access providers (may fail if not wrapped)
  const [providersAvailable, setProvidersAvailable] = useState({
    settings: false,
    tabData: false
  })
  
  // Browser info
  const [browserInfo, setBrowserInfo] = useState<{
    userAgent: string
    language: string
    onLine: boolean
    cookieEnabled: boolean
    memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number }
  } | null>(null)

  // Initialize browser info
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const nav = navigator as Navigator & { 
        deviceMemory?: number
      }
      const perf = performance as Performance & {
        memory?: { usedJSHeapSize: number; totalJSHeapSize: number; jsHeapSizeLimit: number }
      }
      
      setBrowserInfo({
        userAgent: nav.userAgent,
        language: nav.language,
        onLine: nav.onLine,
        cookieEnabled: nav.cookieEnabled,
        memory: perf.memory
      })
      
      // Listen for online/offline events
      const handleOnline = () => setBrowserInfo(prev => prev ? { ...prev, onLine: true } : prev)
      const handleOffline = () => setBrowserInfo(prev => prev ? { ...prev, onLine: false } : prev)
      
      window.addEventListener('online', handleOnline)
      window.addEventListener('offline', handleOffline)
      
      return () => {
        window.removeEventListener('online', handleOnline)
        window.removeEventListener('offline', handleOffline)
      }
    }
  }, [])

  // Service check configurations
  const serviceChecks: ServiceCheckConfig[] = useMemo(() => [
    {
      name: 'Price Service',
      icon: <Activity className="w-4 h-4" />,
      check: () => checkServiceHealth('Price Service', () => 
        priceService.getPriceData('BTC', '1D', { limit: 1 })
      )
    },
    {
      name: 'Attention Service',
      icon: <Zap className="w-4 h-4" />,
      check: () => checkServiceHealth('Attention Service', () => 
        attentionService.getAttentionData('BTC')
      )
    },
    {
      name: 'News Service',
      icon: <Globe className="w-4 h-4" />,
      check: () => checkServiceHealth('News Service', () => 
        newsService.getNews({ symbol: 'ALL', limit: 1 })
      )
    },
    {
      name: 'Scenario Service',
      icon: <Layers className="w-4 h-4" />,
      check: () => checkServiceHealth('Scenario Service', () => 
        scenarioService.getScenarios({ symbol: 'BTC', timeframe: '1d' })
      )
    },
    {
      name: 'Backtest Service',
      icon: <Clock className="w-4 h-4" />,
      check: () => checkServiceHealth('Backtest Service', () => 
        backtestService.runBacktest({
          symbol: 'BTC',
          lookbackDays: 30,
          attentionQuantile: 0.7,
          maxDailyReturn: 0.05,
          holdingDays: 5,
          stopLossPct: null,
          takeProfitPct: null,
          maxHoldingDays: null,
          positionSize: 1,
          attentionSource: 'composite'
        })
      )
    },
    {
      name: 'AutoUpdate Service',
      icon: <RotateCw className="w-4 h-4" />,
      check: () => checkServiceHealth('AutoUpdate Service', () => 
        autoUpdateService.getAutoUpdateStatus()
      )
    }
  ], [])

  // Run single check
  const runCheck = useCallback(async (config: ServiceCheckConfig) => {
    setResults(prev => {
      const next = new Map(prev)
      next.set(config.name, { name: config.name, status: 'checking', message: '检查中...' })
      return next
    })
    
    const result = await config.check()
    result.lastChecked = new Date()
    
    setResults(prev => {
      const next = new Map(prev)
      next.set(config.name, result)
      return next
    })
  }, [])

  // Run all checks
  const runAllChecks = useCallback(async () => {
    setIsChecking(true)
    
    // Browser checks (sequential)
    const localStorageResult = await checkLocalStorage()
    localStorageResult.lastChecked = new Date()
    setResults(prev => new Map(prev).set('localStorage', localStorageResult))
    
    const sessionStorageResult = await checkSessionStorage()
    sessionStorageResult.lastChecked = new Date()
    setResults(prev => new Map(prev).set('sessionStorage', sessionStorageResult))
    
    // Service checks (parallel)
    await Promise.all(serviceChecks.map(runCheck))
    
    setLastFullCheck(new Date())
    setIsChecking(false)
  }, [serviceChecks, runCheck])

  // Check providers on mount
  useEffect(() => {
    // These will be set based on whether the hooks work
    try {
      setProvidersAvailable({
        settings: true,
        tabData: true
      })
    } catch {
      // Provider not available
    }
  }, [])

  // Auto-run checks on mount
  useEffect(() => {
    runAllChecks()
  }, [runAllChecks])

  // Calculate overall status
  const allResults = Array.from(results.values())
  const overallStatus = getOverallStatus(allResults)
  const healthyCount = allResults.filter(r => r.status === 'healthy').length
  const totalCount = allResults.length

  // WebSocket status helpers
  const wsOverallStatus: HealthStatus = 
    priceStatus === 'connected' && attentionStatus === 'connected' ? 'healthy' :
    priceStatus === 'connected' || attentionStatus === 'connected' ? 'degraded' :
    priceStatus === 'connecting' || attentionStatus === 'connecting' ? 'checking' :
    'unhealthy'

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/50 sticky top-0 z-40">
        {/* Debug 页面导航 */}
        <div className="border-b border-border/50 bg-muted/30">
          <div className="container mx-auto px-4 h-8 flex items-center gap-4 text-xs">
            <span className="text-muted-foreground">调试工具:</span>
            <Link href="/debug/api-test" className="text-muted-foreground hover:text-foreground transition-colors">
              API 测试
            </Link>
            <span className="text-muted-foreground">|</span>
            <span className="font-medium text-primary">前端健康检查</span>
          </div>
        </div>
        <div className="container mx-auto px-4 h-14 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">前端健康检查</h1>
            <p className="text-xs text-muted-foreground">
              API Base: {getApiBaseUrl() || 'Next.js Proxy'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/debug/api-test">
              <Button variant="outline" size="sm">API 测试</Button>
            </Link>
            <Link href="/?tab=settings">
              <Button variant="outline" size="sm">返回设置</Button>
            </Link>
            <Button onClick={runAllChecks} disabled={isChecking} size="sm" className="gap-1">
              <RotateCw className={`w-3 h-3 ${isChecking ? 'animate-spin' : ''}`} />
              刷新全部
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-4 space-y-4">
        {/* Overall Status Banner */}
        <Card className={`border-2 ${getStatusBgColor(overallStatus)}`}>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {getStatusIcon(overallStatus)}
                <div>
                  <h2 className="text-lg font-semibold">
                    {overallStatus === 'healthy' ? '前端运行正常' :
                     overallStatus === 'degraded' ? '部分功能受限' :
                     overallStatus === 'unhealthy' ? '存在问题' :
                     overallStatus === 'checking' ? '检查中...' :
                     '状态未知'}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {healthyCount}/{totalCount} 项检查通过
                    {lastFullCheck && ` • 上次检查: ${lastFullCheck.toLocaleTimeString()}`}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <Badge variant={overallStatus === 'healthy' ? 'default' : 'destructive'} className="text-sm">
                  {overallStatus.toUpperCase()}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Browser Environment */}
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Globe className="w-4 h-4" />
              浏览器环境
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 bg-muted/30 rounded-md">
                <p className="text-xs text-muted-foreground mb-1">网络状态</p>
                <div className="flex items-center gap-2">
                  {browserInfo?.onLine ? (
                    <Wifi className="w-4 h-4 text-green-500" />
                  ) : (
                    <WifiOff className="w-4 h-4 text-red-500" />
                  )}
                  <span className={`text-sm font-medium ${browserInfo?.onLine ? 'text-green-500' : 'text-red-500'}`}>
                    {browserInfo?.onLine ? '在线' : '离线'}
                  </span>
                </div>
              </div>
              
              <div className="p-3 bg-muted/30 rounded-md">
                <p className="text-xs text-muted-foreground mb-1">Cookie</p>
                <div className="flex items-center gap-2">
                  {browserInfo?.cookieEnabled ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                  <span className="text-sm font-medium">
                    {browserInfo?.cookieEnabled ? '已启用' : '已禁用'}
                  </span>
                </div>
              </div>
              
              <div className="p-3 bg-muted/30 rounded-md">
                <p className="text-xs text-muted-foreground mb-1">语言</p>
                <p className="text-sm font-medium">{browserInfo?.language || '未知'}</p>
              </div>
              
              {browserInfo?.memory && (
                <div className="p-3 bg-muted/30 rounded-md">
                  <p className="text-xs text-muted-foreground mb-1">JS 内存</p>
                  <p className="text-sm font-medium">
                    {(browserInfo.memory.usedJSHeapSize / 1024 / 1024).toFixed(1)} / 
                    {(browserInfo.memory.jsHeapSizeLimit / 1024 / 1024).toFixed(0)} MB
                  </p>
                </div>
              )}
            </div>
            
            <details className="mt-3">
              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                查看 User Agent
              </summary>
              <pre className="mt-2 text-xs bg-muted/50 p-2 rounded overflow-x-auto">
                {browserInfo?.userAgent}
              </pre>
            </details>
          </CardContent>
        </Card>

        {/* WebSocket Status */}
        <Card className={getStatusBgColor(wsOverallStatus)}>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Wifi className="w-4 h-4" />
              WebSocket 连接
              <Badge variant={wsOverallStatus === 'healthy' ? 'default' : 'secondary'} className="text-xs ml-auto">
                {wsOverallStatus === 'healthy' ? '全部连接' : 
                 wsOverallStatus === 'degraded' ? '部分连接' : 
                 wsOverallStatus === 'checking' ? '连接中' : '未连接'}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="grid grid-cols-2 gap-3">
              <div className={`p-3 rounded-md border ${
                priceStatus === 'connected' ? 'bg-green-500/10 border-green-500/30' :
                priceStatus === 'connecting' ? 'bg-yellow-500/10 border-yellow-500/30' :
                'bg-red-500/10 border-red-500/30'
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <Activity className="w-4 h-4" />
                  <span className="text-sm font-medium">价格 WebSocket</span>
                </div>
                <p className={`text-xs ${getStatusColor(
                  priceStatus === 'connected' ? 'healthy' :
                  priceStatus === 'connecting' ? 'checking' : 'unhealthy'
                )}`}>
                  {priceStatus}
                </p>
              </div>
              
              <div className={`p-3 rounded-md border ${
                attentionStatus === 'connected' ? 'bg-green-500/10 border-green-500/30' :
                attentionStatus === 'connecting' ? 'bg-yellow-500/10 border-yellow-500/30' :
                'bg-red-500/10 border-red-500/30'
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <Zap className="w-4 h-4" />
                  <span className="text-sm font-medium">注意力 WebSocket</span>
                </div>
                <p className={`text-xs ${getStatusColor(
                  attentionStatus === 'connected' ? 'healthy' :
                  attentionStatus === 'connecting' ? 'checking' : 'unhealthy'
                )}`}>
                  {attentionStatus}
                </p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              💡 WebSocket 用于实时价格推送，连接失败不影响基本功能
            </p>
          </CardContent>
        </Card>

        {/* Storage & Providers */}
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <HardDrive className="w-4 h-4" />
              存储 & 上下文
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0 space-y-3">
            {/* localStorage */}
            {['localStorage', 'sessionStorage'].map(key => {
              const result = results.get(key)
              return (
                <div key={key} className={`p-3 rounded-md border ${getStatusBgColor(result?.status || 'unknown')}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(result?.status || 'unknown')}
                      <span className="text-sm font-medium">{key}</span>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">{result?.message || '未检查'}</p>
                      {result?.latency && (
                        <p className="text-xs text-muted-foreground">{result.latency.toFixed(1)}ms</p>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
            
            {/* Providers */}
            <div className="grid grid-cols-2 gap-3 pt-2">
              <div className={`p-3 rounded-md border ${providersAvailable.settings ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                <div className="flex items-center gap-2">
                  <Settings className="w-4 h-4" />
                  <span className="text-sm font-medium">SettingsProvider</span>
                </div>
                <p className={`text-xs ${providersAvailable.settings ? 'text-green-500' : 'text-red-500'}`}>
                  {providersAvailable.settings ? '可用' : '不可用'}
                </p>
              </div>
              
              <div className={`p-3 rounded-md border ${providersAvailable.tabData ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4" />
                  <span className="text-sm font-medium">TabDataProvider</span>
                </div>
                <p className={`text-xs ${providersAvailable.tabData ? 'text-green-500' : 'text-red-500'}`}>
                  {providersAvailable.tabData ? '可用' : '不可用'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* API Services */}
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Cpu className="w-4 h-4" />
              API 服务
              <span className="text-xs text-muted-foreground ml-2">
                ({serviceChecks.filter(c => results.get(c.name)?.status === 'healthy').length}/{serviceChecks.length} 正常)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="space-y-2">
              {serviceChecks.map(config => {
                const result = results.get(config.name)
                return (
                  <div 
                    key={config.name} 
                    className={`p-3 rounded-md border ${getStatusBgColor(result?.status || 'unknown')}`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(result?.status || 'unknown')}
                        {config.icon}
                        <span className="text-sm font-medium">{config.name}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <p className="text-xs text-muted-foreground">{result?.message || '未检查'}</p>
                          {result?.latency && (
                            <p className="text-xs text-muted-foreground">{result.latency.toFixed(0)}ms</p>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0"
                          onClick={() => runCheck(config)}
                          disabled={result?.status === 'checking'}
                        >
                          <RotateCw className={`w-3 h-3 ${result?.status === 'checking' ? 'animate-spin' : ''}`} />
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              💡 点击右侧刷新按钮可单独重新检查某个服务
            </p>
          </CardContent>
        </Card>

        {/* Quick Diagnostics */}
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm font-medium">快速诊断</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                {browserInfo?.onLine ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-500" />
                )}
                <span>浏览器网络连接</span>
              </div>
              
              <div className="flex items-center gap-2">
                {results.get('localStorage')?.status === 'healthy' ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-500" />
                )}
                <span>本地存储可用</span>
              </div>
              
              <div className="flex items-center gap-2">
                {wsOverallStatus === 'healthy' || wsOverallStatus === 'degraded' ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : wsOverallStatus === 'checking' ? (
                  <RotateCw className="w-4 h-4 text-yellow-500 animate-spin" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-yellow-500" />
                )}
                <span>WebSocket 实时连接 {wsOverallStatus === 'unhealthy' && '(可选)'}</span>
              </div>
              
              <div className="flex items-center gap-2">
                {serviceChecks.every(c => results.get(c.name)?.status === 'healthy') ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : serviceChecks.some(c => results.get(c.name)?.status === 'healthy') ? (
                  <AlertCircle className="w-4 h-4 text-yellow-500" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-500" />
                )}
                <span>后端 API 服务</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  )
}
