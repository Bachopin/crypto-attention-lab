/* eslint-disable react/display-name */
'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'

// ==================== 安全导入 ====================
// Debug 页面使用安全导入，确保即使某些模块有问题也能渲染

// UI 组件 - 使用 try/catch 包装，提供回退
let Card: any, CardContent: any, CardHeader: any, CardTitle: any
let Button: any, Badge: any
try {
  const ui = require('@/components/ui/card')
  Card = ui.Card
  CardContent = ui.CardContent
  CardHeader = ui.CardHeader
  CardTitle = ui.CardTitle
} catch {
  Card = ({ children, className }: any) => <div className={`border rounded-lg ${className || ''}`}>{children}</div>
  CardContent = ({ children, className }: any) => <div className={`p-4 ${className || ''}`}>{children}</div>
  CardHeader = ({ children, className }: any) => <div className={`p-4 border-b ${className || ''}`}>{children}</div>
  CardTitle = ({ children, className }: any) => <h3 className={`font-semibold ${className || ''}`}>{children}</h3>
}

try {
  Button = require('@/components/ui/button').Button
} catch {
  Button = ({ children, onClick, disabled, className }: any) => (
    <button onClick={onClick} disabled={disabled} className={`px-3 py-1.5 rounded border ${disabled ? 'opacity-50' : ''} ${className || ''}`}>
      {children}
    </button>
  )
}

try {
  Badge = require('@/components/ui/badge').Badge
} catch {
  Badge = ({ children, variant, className }: any) => (
    <span className={`px-2 py-0.5 text-xs rounded ${className || ''}`}>{children}</span>
  )
}

// 图标 - 使用安全导入
let ChevronDown: any, ChevronRight: any, Play: any, RotateCw: any
let Wifi: any, WifiOff: any, Radio: any, Clock: any

try {
  const icons = require('lucide-react')
  ChevronDown = icons.ChevronDown
  ChevronRight = icons.ChevronRight
  Play = icons.Play
  RotateCw = icons.RotateCw
  Wifi = icons.Wifi
  WifiOff = icons.WifiOff
  Radio = icons.Radio
  Clock = icons.Clock
} catch {
  const FallbackIcon = ({ className }: { className?: string }) => <span className={className}>●</span>
  ChevronDown = () => <span>▼</span>
  ChevronRight = () => <span>▶</span>
  Play = FallbackIcon
  RotateCw = FallbackIcon
  Wifi = FallbackIcon
  WifiOff = FallbackIcon
  Radio = FallbackIcon
  Clock = FallbackIcon
}

// API helpers - 安全导入
let buildApiUrl: (path: string) => string
let getApiBaseUrl: () => string
try {
  const api = require('@/lib/api')
  buildApiUrl = api.buildApiUrl
  getApiBaseUrl = api.getApiBaseUrl
} catch {
  buildApiUrl = (path: string) => `http://127.0.0.1:8000${path}`
  getApiBaseUrl = () => 'http://127.0.0.1:8000'
}

// RealtimePrice 组件 - 安全导入
let RealtimePriceTicker: any
let useWebSocketStatus: () => { priceStatus: string; attentionStatus: string }
try {
  RealtimePriceTicker = require('@/components/RealtimePrice').RealtimePriceTicker
} catch {
  RealtimePriceTicker = ({ symbol }: { symbol: string }) => (
    <span className="text-muted-foreground text-sm">价格组件不可用</span>
  )
}

try {
  useWebSocketStatus = require('@/lib/websocket').useWebSocketStatus
} catch {
  useWebSocketStatus = () => ({ priceStatus: 'unavailable', attentionStatus: 'unavailable' })
}

// 安全的 RealtimePriceTicker 包装组件
function SafeRealtimePriceTicker({ symbol }: { symbol: string }) {
  try {
    return <RealtimePriceTicker symbol={symbol} size="sm" showChange={false} />
  } catch (e) {
    return <span className="text-muted-foreground text-xs">加载失败</span>
  }
}

interface ApiRequestConfig {
  key: string
  label: string
  path: string
  description: string
  category: string
}

interface ApiTestResult {
  key: string
  label: string
  requestUrl: string
  description: string
  category: string
  status?: number
  statusText?: string
  ok: boolean
  durationMs?: number
  bodyPreview?: string
  error?: string
}

// 按类别组织的 API 列表
// 注意：这些路径通过 Next.js rewrites 代理到后端 (next.config.ts)
const REQUESTS: ApiRequestConfig[] = [
  // 基础数据
  { key: 'health', label: '/health', path: '/health', description: '健康检查', category: '基础' },
  { key: 'ping', label: '/ping', path: '/ping', description: 'Ping 测试', category: '基础' },
  { key: 'symbols', label: '/api/symbols', path: '/api/symbols', description: '获取可用代币列表', category: '基础' },
  { key: 'top-coins', label: '/api/top-coins', path: '/api/top-coins?limit=10', description: 'CoinGecko 市值前10', category: '基础' },
  { key: 'auto-update-status', label: '/api/auto-update/status', path: '/api/auto-update/status', description: '自动更新状态', category: '基础' },
  
  // 价格数据
  { key: 'price-1d', label: '/api/price (1D)', path: '/api/price?symbol=ZECUSDT&timeframe=1d', description: 'ZEC 日线 K线', category: '价格' },
  { key: 'price-4h', label: '/api/price (4H)', path: '/api/price?symbol=BTCUSDT&timeframe=4h', description: 'BTC 4小时 K线', category: '价格' },
  { key: 'price-1h', label: '/api/price (1H)', path: '/api/price?symbol=ETHUSDT&timeframe=1h', description: 'ETH 1小时 K线', category: '价格' },
  
  // 注意力数据
  { key: 'attention', label: '/api/attention', path: '/api/attention?symbol=ZEC&granularity=1d', description: 'ZEC 日度注意力分数', category: '注意力' },
  { key: 'attention-events', label: '/api/attention-events', path: '/api/attention-events?symbol=ZEC&lookback_days=30', description: 'ZEC 注意力事件', category: '注意力' },
  { key: 'attention-events-perf', label: '/api/attention-events/performance', path: '/api/attention-events/performance?symbol=ZEC', description: '注意力事件表现统计', category: '注意力' },
  
  // 新闻数据
  { key: 'news', label: '/api/news', path: '/api/news?symbol=ZEC&limit=5', description: 'ZEC 相关新闻', category: '新闻' },
  { key: 'news-all', label: '/api/news (ALL)', path: '/api/news?symbol=ALL&limit=10', description: '全部新闻', category: '新闻' },
  { key: 'news-count', label: '/api/news/count', path: '/api/news/count?symbol=ALL', description: '新闻总数（缓存）', category: '新闻' },
  { key: 'news-stats-hourly', label: '/api/news/stats/hourly', path: '/api/news/stats/hourly?limit=24', description: '每小时新闻统计', category: '新闻' },
  { key: 'news-stats-daily', label: '/api/news/stats/daily', path: '/api/news/stats/daily?limit=7', description: '每日新闻统计', category: '新闻' },
  { key: 'news-trend', label: '/api/news/trend', path: '/api/news/trend?symbol=ALL&interval=1d', description: '新闻趋势', category: '新闻' },
  
  // 研究分析
  { key: 'node-influence', label: '/api/node-influence', path: '/api/node-influence?symbol=ZEC&limit=10', description: '节点带货因子', category: '研究' },
  { key: 'state-snapshot', label: '/api/state/snapshot', path: '/api/state/snapshot?symbol=ZEC&timeframe=1d', description: '状态快照', category: '研究' },
  { key: 'similar-cases', label: '/api/state/similar-cases', path: '/api/state/similar-cases?symbol=ZEC&timeframe=1d', description: '相似历史状态', category: '研究' },
  { key: 'scenarios', label: '/api/state/scenarios', path: '/api/state/scenarios?symbol=ZEC&timeframe=1d', description: '情景分析', category: '研究' },
  
  // 管理
  { key: 'ws-stats', label: '/api/ws/stats', path: '/api/ws/stats', description: 'WebSocket 连接统计', category: '管理' },
]

const CATEGORIES = ['基础', '价格', '注意力', '新闻', '研究', '管理']

// 实时更新测试配置
const REALTIME_TEST_SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB']

// 更新频率配置（与实际实现保持一致）
// 参考：docs/backend/AUTO_UPDATE_MECHANISM.md
const UPDATE_INTERVALS = [
  { name: '实时价格', source: 'WebSocket', interval: '实时推送', description: 'Dashboard SummaryCard 价格' },
  { name: '价格数据', source: 'REST API', interval: '10 分钟', description: 'K线数据，多标的错峰更新' },
  { name: '特征值', source: 'REST API', interval: '1 小时冷却', description: '注意力分数等特征值计算' },
  { name: 'Google Trends', source: 'REST API', interval: '12 小时冷却', description: '热度趋势数据' },
  { name: '新闻数据', source: 'REST API', interval: '1 小时', description: '全局新闻抓取' },
]

const MAX_BODY_LENGTH = 1500
const REQUEST_TIMEOUT_MS = 30000  // 30秒超时（注意力事件按需更新可能需要较长时间）

function formatBody(rawBody: string): string {
  if (!rawBody) return '[empty response]'
  let pretty = rawBody
  try {
    const parsed = JSON.parse(rawBody)
    pretty = JSON.stringify(parsed, null, 2)
  } catch {
    // not JSON
  }
  if (pretty.length > MAX_BODY_LENGTH) {
    return `${pretty.slice(0, MAX_BODY_LENGTH)}\n... (truncated) ...`
  }
  return pretty
}

export default function ApiTestPage() {
  const [results, setResults] = useState<Map<string, ApiTestResult>>(new Map())
  const [testing, setTesting] = useState<Set<string>>(new Set())
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [resolvedApiBase, setResolvedApiBase] = useState<string>('加载中...')

  useEffect(() => {
    setResolvedApiBase(getApiBaseUrl() || 'Next.js proxy (/api → backend)')
  }, [])

  const runSingleTest = useCallback(async (config: ApiRequestConfig) => {
    setTesting(prev => new Set(prev).add(config.key))
    
    const requestUrl = buildApiUrl(config.path)
    const startedAt = performance.now()
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

    try {
      const response = await fetch(requestUrl, { signal: controller.signal })
      clearTimeout(timeoutId)
      const duration = performance.now() - startedAt
      const bodyText = await response.text()

      const result: ApiTestResult = {
        key: config.key,
        label: config.label,
        requestUrl,
        description: config.description,
        category: config.category,
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        durationMs: duration,
        bodyPreview: formatBody(bodyText),
      }
      setResults(prev => new Map(prev).set(config.key, result))
      setExpanded(prev => new Set(prev).add(config.key)) // 自动展开刚测试的
    } catch (error) {
      clearTimeout(timeoutId)
      const duration = performance.now() - startedAt
      let errorMsg = 'Unknown error'
      if (error instanceof Error) {
        errorMsg = error.name === 'AbortError' 
          ? `超时 (>${REQUEST_TIMEOUT_MS / 1000}s)` 
          : error.message
      }
      const result: ApiTestResult = {
        key: config.key,
        label: config.label,
        requestUrl,
        description: config.description,
        category: config.category,
        ok: false,
        durationMs: duration,
        error: errorMsg,
      }
      setResults(prev => new Map(prev).set(config.key, result))
      setExpanded(prev => new Set(prev).add(config.key))
    } finally {
      setTesting(prev => {
        const next = new Set(prev)
        next.delete(config.key)
        return next
      })
    }
  }, [])

  const runAllTests = useCallback(async () => {
    setExpanded(new Set()) // 折叠所有
    for (const config of REQUESTS) {
      await runSingleTest(config)
    }
  }, [runSingleTest])

  const runCategoryTests = useCallback(async (category: string) => {
    const configs = REQUESTS.filter(r => r.category === category)
    for (const config of configs) {
      await runSingleTest(config)
    }
  }, [runSingleTest])

  const toggleExpand = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const getResultForKey = (key: string) => results.get(key)
  
  // 检测是否在 Codespaces 环境
  const [isCodespaces, setIsCodespaces] = useState(false)
  useEffect(() => {
    if (typeof window !== 'undefined') {
      setIsCodespaces(window.location.hostname.includes('github.dev') || 
                      window.location.hostname.includes('app.github.dev'))
    }
  }, [])

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/50 sticky top-0 z-40">
        {/* Debug 页面导航 */}
        <div className="border-b border-border/50 bg-muted/30">
          <div className="container mx-auto px-4 h-8 flex items-center gap-4 text-xs">
            <span className="text-muted-foreground">调试工具:</span>
            <span className="font-medium text-primary">API 测试</span>
            <span className="text-muted-foreground">|</span>
            <Link href="/debug/frontend-health" className="text-muted-foreground hover:text-foreground transition-colors">
              前端健康检查
            </Link>
          </div>
        </div>
        <div className="container mx-auto px-4 h-14 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">API 调试工具</h1>
            <p className="text-xs text-muted-foreground">Base: {resolvedApiBase}</p>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/debug/frontend-health">
              <Button variant="outline" size="sm">前端健康</Button>
            </Link>
            <Link href="/?tab=settings">
              <Button variant="outline" size="sm">返回设置</Button>
            </Link>
            <Button onClick={runAllTests} disabled={testing.size > 0} size="sm" className="gap-1">
              <RotateCw className={`w-3 h-3 ${testing.size > 0 ? 'animate-spin' : ''}`} />
              测试全部
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-4 space-y-4">
        {/* Codespaces 环境提示 */}
        {isCodespaces && (
          <Card className="border-yellow-500/50 bg-yellow-500/10">
            <CardContent className="py-3">
              <p className="text-sm text-yellow-600 dark:text-yellow-400">
                ⚠️ <strong>Codespaces 环境</strong>：外部浏览器访问时，API 请求需要通过 Codespaces 端口转发。
                请确保端口 3000 和 8000 已设置为 Public，或使用 VS Code 内置浏览器测试。
              </p>
            </CardContent>
          </Card>
        )}
        
        {/* 实时更新测试区域 */}
        <RealtimeUpdateTestSection />
        
        {CATEGORIES.map(category => {
          const categoryRequests = REQUESTS.filter(r => r.category === category)
          const categoryResults = categoryRequests.map(r => getResultForKey(r.key)).filter(Boolean)
          const successCount = categoryResults.filter(r => r?.ok).length
          const failCount = categoryResults.filter(r => r && !r.ok).length
          
          return (
            <Card key={category}>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    {category}
                    <span className="text-xs text-muted-foreground">
                      ({categoryRequests.length} 个接口)
                    </span>
                    {successCount > 0 && (
                      <Badge variant="default" className="text-xs">{successCount} ✓</Badge>
                    )}
                    {failCount > 0 && (
                      <Badge variant="destructive" className="text-xs">{failCount} ✗</Badge>
                    )}
                  </CardTitle>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => runCategoryTests(category)}
                    disabled={testing.size > 0}
                    className="h-7 text-xs"
                  >
                    测试此类
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-3 pt-0">
                <div className="space-y-1">
                  {categoryRequests.map(config => {
                    const result = getResultForKey(config.key)
                    const isExpanded = expanded.has(config.key)
                    const isTesting = testing.has(config.key)
                    
                    return (
                      <div key={config.key} className="border rounded-md overflow-hidden">
                        {/* 标题行 - 可点击展开 */}
                        <div 
                          className="flex items-center justify-between px-3 py-2 bg-muted/30 cursor-pointer hover:bg-muted/50"
                          onClick={() => result && toggleExpand(config.key)}
                        >
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            {result ? (
                              isExpanded ? <ChevronDown className="w-4 h-4 shrink-0" /> : <ChevronRight className="w-4 h-4 shrink-0" />
                            ) : (
                              <span className="w-4 h-4 shrink-0" />
                            )}
                            <code className="text-xs font-mono truncate">{config.label}</code>
                            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
                              - {config.description}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            {result && (
                              <>
                                <Badge variant={result.ok ? 'default' : 'destructive'} className="text-xs">
                                  {result.ok ? `${result.status}` : 'Failed'}
                                </Badge>
                                <span className="text-xs text-muted-foreground w-14 text-right">
                                  {result.durationMs?.toFixed(0)} ms
                                </span>
                              </>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={(e: React.MouseEvent) => {
                                e.stopPropagation()
                                runSingleTest(config)
                              }}
                              disabled={isTesting}
                            >
                              {isTesting ? (
                                <RotateCw className="w-3 h-3 animate-spin" />
                              ) : (
                                <Play className="w-3 h-3" />
                              )}
                            </Button>
                          </div>
                        </div>
                        
                        {/* 展开的详情 */}
                        {result && isExpanded && (
                          <div className="px-3 py-2 border-t bg-background">
                            <p className="text-xs text-muted-foreground mb-2 break-all">
                              URL: <span className="font-mono">{result.requestUrl}</span>
                            </p>
                            {result.error ? (
                              <pre className="text-xs text-red-500 whitespace-pre-wrap">
                                {result.error}
                              </pre>
                            ) : (
                              <pre className="text-xs whitespace-pre-wrap break-all bg-muted rounded p-2 max-h-64 overflow-auto">
                                {result.bodyPreview}
                              </pre>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </main>
    </div>
  )
}

/**
 * 实时更新测试区域
 * 测试 WebSocket 连接和自动刷新功能
 * 使用 try/catch 包装确保组件始终能渲染
 */
function RealtimeUpdateTestSection() {
  // 安全调用 hook
  let priceStatus = 'unavailable'
  let attentionStatus = 'unavailable'
  try {
    const wsStatus = useWebSocketStatus()
    priceStatus = wsStatus.priceStatus
    attentionStatus = wsStatus.attentionStatus
  } catch (e) {
    console.warn('[Debug] WebSocket status hook failed:', e)
  }

  const [restTestResults, setRestTestResults] = useState<{
    lastUpdate: Date | null
    countdown: number
    isUpdating: boolean
  }>({ lastUpdate: null, countdown: 0, isUpdating: false })
  const [precompStatus, setPrecompStatus] = useState<any>(null)
  const [sectionError, setSectionError] = useState<string | null>(null)
  
  // 模拟 10 分钟倒计时（与实际 PRICE_UPDATE_INTERVAL 一致）
  useEffect(() => {
    try {
      const interval = setInterval(() => {
        setRestTestResults(prev => {
          if (prev.countdown <= 0) {
            return { ...prev, countdown: 600, lastUpdate: new Date(), isUpdating: false }
          }
          return { ...prev, countdown: prev.countdown - 1 }
        })
      }, 1000)
      
      // 初始化
      setRestTestResults({ lastUpdate: new Date(), countdown: 600, isUpdating: false })
      
      return () => clearInterval(interval)
    } catch (e) {
      setSectionError(`Timer error: ${e}`)
    }
  }, [])

  // 拉取预计算状态（用于 Debug 面板显示更新时间）
  useEffect(() => {
    let mounted = true
    async function fetchStatus() {
      try {
        const url = buildApiUrl('/api/precomputation/status?symbol=ZEC')
        const resp = await fetch(url)
        if (!mounted) return
        if (resp.ok) {
          const json = await resp.json()
          setPrecompStatus(json)
        } else {
          setPrecompStatus({ error: `Status ${resp.status}` })
        }
      } catch (err) {
        if (mounted) {
          setPrecompStatus({ error: (err as Error).message })
        }
      }
    }

    fetchStatus()
    // 定期刷新（每 60s）
    const t = setInterval(fetchStatus, 60000)
    return () => {
      mounted = false
      clearInterval(t)
    }
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'text-green-500'
      case 'connecting': return 'text-yellow-500'
      case 'error': return 'text-red-500'
      default: return 'text-muted-foreground'
    }
  }

  const getStatusIcon = (status: string) => {
    try {
      switch (status) {
        case 'connected': return <Wifi className="w-4 h-4" />
        case 'connecting': return <Radio className="w-4 h-4 animate-pulse" />
        default: return <WifiOff className="w-4 h-4" />
      }
    } catch {
      return <span>●</span>
    }
  }

  // 如果整个区域有错误，显示简化版本
  if (sectionError) {
    return (
      <Card className="border-yellow-500/30 bg-yellow-500/5">
        <CardContent className="py-4">
          <p className="text-sm text-yellow-500">实时更新测试区域加载失败: {sectionError}</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
      <CardHeader className="py-3 px-4">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Radio className="w-4 h-4 text-primary" />
          实时更新测试
          <Badge variant="outline" className="text-xs ml-2">新功能</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 pt-0 space-y-4">
        {/* WebSocket 状态 */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">WebSocket 连接状态</h4>
          <div className="grid grid-cols-2 gap-2">
            <div className="flex items-center gap-2 p-2 bg-muted/30 rounded-md">
              <span className={getStatusColor(priceStatus)}>
                {getStatusIcon(priceStatus)}
              </span>
              <div>
                <p className="text-xs font-medium">价格 WebSocket</p>
                <p className={`text-xs ${getStatusColor(priceStatus)}`}>{priceStatus}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 bg-muted/30 rounded-md">
              <span className={getStatusColor(attentionStatus)}>
                {getStatusIcon(attentionStatus)}
              </span>
              <div>
                <p className="text-xs font-medium">注意力 WebSocket</p>
                <p className={`text-xs ${getStatusColor(attentionStatus)}`}>{attentionStatus}</p>
              </div>
            </div>
          </div>
        </div>

        {/* 实时价格测试 */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">实时价格 (WebSocket)</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {REALTIME_TEST_SYMBOLS.map(symbol => (
              <div key={symbol} className="p-3 bg-muted/30 rounded-md">
                <p className="text-xs font-medium text-muted-foreground mb-1">{symbol}/USDT</p>
                <SafeRealtimePriceTicker symbol={symbol} />
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            💡 如果显示 &quot;LIVE&quot; 标记并有价格闪烁，说明 WebSocket 连接正常
          </p>
        </div>

        {/* 自动刷新机制 */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">自动刷新机制</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-2 font-medium">数据类型</th>
                  <th className="text-left py-2 px-2 font-medium">数据源</th>
                  <th className="text-left py-2 px-2 font-medium">刷新间隔</th>
                  <th className="text-left py-2 px-2 font-medium">说明</th>
                </tr>
              </thead>
              <tbody>
                {UPDATE_INTERVALS.map((item, idx) => (
                  <tr key={idx} className="border-b border-border/50">
                    <td className="py-2 px-2 font-medium">{item.name}</td>
                    <td className="py-2 px-2">
                      <Badge variant={item.source === 'WebSocket' ? 'default' : 'secondary'} className="text-xs">
                        {item.source}
                      </Badge>
                    </td>
                    <td className="py-2 px-2">{item.interval}</td>
                    <td className="py-2 px-2 text-muted-foreground">{item.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* REST 轮询模拟 */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">REST 轮询状态</h4>
          <div className="flex items-center gap-4 p-3 bg-muted/30 rounded-md">
            <Clock className="w-5 h-5 text-primary" />
            <div className="flex-1">
              <p className="text-sm font-medium">下次价格数据刷新周期</p>
              <p className="text-xs text-muted-foreground">
                上次更新: {restTestResults.lastUpdate?.toLocaleTimeString() || '未知'}
              </p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-mono font-bold text-primary">
                {Math.floor(restTestResults.countdown / 60)}:{(restTestResults.countdown % 60).toString().padStart(2, '0')}
              </p>
              <p className="text-xs text-muted-foreground">剩余时间</p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            💡 多标的采用<strong>错峰更新</strong>策略：间隔 = (10min × 0.8) / 标的数量
          </p>
        </div>

        {/* 预计算状态展示 */}
        <div className="space-y-2">
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">预计算状态</h4>
          <div className="p-3 bg-muted/30 rounded-md text-xs">
            {precompStatus ? (
              precompStatus.error ? (
                <p className="text-red-500">{precompStatus.error}</p>
              ) : (
                <div className="grid grid-cols-1 gap-1">
                  <div>Symbol: <strong>{precompStatus.symbol}</strong></div>
                  <div>Price last update: <code className="font-mono">{precompStatus.price_last_update ?? 'N/A'}</code></div>
                  <div>Attention latest datetime: <code className="font-mono">{precompStatus.attention_latest_datetime ?? 'N/A'}</code></div>
                  <div>Event performance updated at: <code className="font-mono">{precompStatus.event_performance_updated_at ?? 'N/A'}</code></div>
                  <div>Latest snapshot (1d): <code className="font-mono">{precompStatus.latest_state_snapshot_1d ?? 'N/A'}</code></div>
                  <div>Latest snapshot (4h): <code className="font-mono">{precompStatus.latest_state_snapshot_4h ?? 'N/A'}</code></div>
                  <div>News total count (cached): <strong>{precompStatus.news_total_count ?? 'N/A'}</strong></div>
                </div>
              )
            ) : (
              <p className="text-muted-foreground">正在加载预计算状态...</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
