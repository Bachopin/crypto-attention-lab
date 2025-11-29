'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { buildApiUrl, getApiBaseUrl } from '@/lib/api'
import { ChevronDown, ChevronRight, Play, RotateCw } from 'lucide-react'

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
const REQUESTS: ApiRequestConfig[] = [
  // 基础数据
  { key: 'health', label: '/health', path: '/health', description: '健康检查', category: '基础' },
  { key: 'ping', label: '/ping', path: '/ping', description: 'Ping 测试', category: '基础' },
  { key: 'root', label: '/', path: '/', description: 'API 根路径', category: '基础' },
  { key: 'symbols', label: '/api/symbols', path: '/api/symbols', description: '获取可用代币列表', category: '基础' },
  { key: 'top-coins', label: '/api/top-coins', path: '/api/top-coins?limit=10', description: 'CoinGecko 市值前10', category: '基础' },
  
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
  { key: 'news-count', label: '/api/news/count', path: '/api/news/count?symbol=ALL', description: '新闻总数', category: '新闻' },
  { key: 'news-trend', label: '/api/news/trend', path: '/api/news/trend?symbol=ALL&interval=1d', description: '新闻趋势', category: '新闻' },
  
  // 研究分析
  { key: 'node-influence', label: '/api/node-influence', path: '/api/node-influence?symbol=ZEC&limit=10', description: '节点带货因子', category: '研究' },
  { key: 'state-snapshot', label: '/api/state/snapshot', path: '/api/state/snapshot?symbol=ZEC&timeframe=1d', description: '状态快照', category: '研究' },
  { key: 'similar-cases', label: '/api/state/similar-cases', path: '/api/state/similar-cases?symbol=ZEC&timeframe=1d', description: '相似历史状态', category: '研究' },
  { key: 'scenarios', label: '/api/state/scenarios', path: '/api/state/scenarios?symbol=ZEC&timeframe=1d', description: '情景分析', category: '研究' },
  
  // 自动更新管理
  { key: 'auto-update-status', label: '/api/auto-update/status', path: '/api/auto-update/status', description: '自动更新状态', category: '管理' },
  { key: 'ws-stats', label: '/api/ws/stats', path: '/api/ws/stats', description: 'WebSocket 连接统计', category: '管理' },
]

const CATEGORIES = ['基础', '价格', '注意力', '新闻', '研究', '管理']

const MAX_BODY_LENGTH = 1500
const REQUEST_TIMEOUT_MS = 10000

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

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/50 sticky top-0 z-40">
        <div className="container mx-auto px-4 h-14 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">API 调试工具</h1>
            <p className="text-xs text-muted-foreground">Base: {resolvedApiBase}</p>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/">
              <Button variant="outline" size="sm">返回主页</Button>
            </Link>
            <Button onClick={runAllTests} disabled={testing.size > 0} size="sm" className="gap-1">
              <RotateCw className={`w-3 h-3 ${testing.size > 0 ? 'animate-spin' : ''}`} />
              测试全部
            </Button>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-4 space-y-4">
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
                              onClick={(e) => {
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
