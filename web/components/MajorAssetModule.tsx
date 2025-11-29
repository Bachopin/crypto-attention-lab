'use client'

/**
 * MajorAssetModule - 单个主流币展示模块
 * 
 * 用于「市场总览」页面，展示单个大币（如 BTC/ETH/BNB/SOL）的：
 * - 顶部信息条：Logo/名称、当前价格、24h变动、Attention状态
 * - 主图区域：价格+成交量图（左）、Attention曲线图（右）
 * - 底部：Regime摘要卡片
 * 
 * 未来扩展：
 * - 支持更多大币（XRP、DOGE等）
 * - 增加更多时间粒度
 * - 增加用户自定义指标
 */

import React, { useEffect, useRef, useState, useCallback, memo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import PriceChart, { PriceChartRef } from '@/components/PriceChart'
import AttentionChart, { AttentionChartRef } from '@/components/AttentionChart'
import { formatNumber, formatPercentage } from '@/lib/utils'
import {
  fetchPrice,
  fetchAttention,
  fetchAttentionEvents,
  fetchAttentionRegimeAnalysis,
  type Timeframe,
  type PriceCandle,
  type AttentionData,
  type AttentionEvent,
  type AttentionRegimeResponse,
} from '@/lib/api'
import { TrendingUp, TrendingDown, Activity, BarChart3 } from 'lucide-react'
import { Range, Time } from 'lightweight-charts'

// 币种图标映射（使用 emoji 作为简易方案，生产环境可替换为真实 logo）
const SYMBOL_ICONS: Record<string, string> = {
  BTC: '₿',
  ETH: 'Ξ',
  BNB: '🔶',
  SOL: '◎',
}

// Attention 状态等级
type AttentionLevel = 'High' | 'Mid' | 'Low'

function getAttentionLevel(zscore: number): AttentionLevel {
  if (zscore >= 1) return 'High'
  if (zscore <= -1) return 'Low'
  return 'Mid'
}

function getAttentionLevelColor(level: AttentionLevel): string {
  switch (level) {
    case 'High': return 'text-red-500'
    case 'Low': return 'text-green-500'
    default: return 'text-yellow-500'
  }
}

interface MajorAssetModuleProps {
  symbol: string // e.g., 'BTC'
  timeframe: Timeframe // 共享的时间粒度
  dateRange: { start?: string; end?: string } // 共享的时间范围
  onCrosshairMove?: (time: Time | null) => void
  crosshairTime?: Time | null
}

interface AssetData {
  priceData: PriceCandle[]
  attentionData: AttentionData[]
  events: AttentionEvent[]
  regimeData: AttentionRegimeResponse | null
  currentPrice: number
  priceChange24h: number
  currentAttention: number
  attentionZscore: number
  initialLoading: boolean  // 仅首次加载时显示 loading
  error: string | null
}

function MajorAssetModuleComponent({
  symbol,
  timeframe,
  dateRange,
  onCrosshairMove,
  crosshairTime,
}: MajorAssetModuleProps) {
  const priceChartRef = useRef<PriceChartRef>(null)
  const attentionChartRef = useRef<AttentionChartRef>(null)

  const [data, setData] = useState<AssetData>({
    priceData: [],
    attentionData: [],
    events: [],
    regimeData: null,
    currentPrice: 0,
    priceChange24h: 0,
    currentAttention: 0,
    attentionZscore: 0,
    initialLoading: true,  // 仅首次加载时显示 loading
    error: null,
  })

  // 市场概况页面：成交量窗格固定为 1/5，不显示控制按钮
  const volumeRatio = 0.2
  const [showEventMarkers, setShowEventMarkers] = useState(true)

  // 使用 ref 存储 crosshairTime，避免因 memo 阻止更新
  const crosshairTimeRef = useRef<Time | null>(crosshairTime ?? null)
  
  // 同步 crosshairTime ref - 这个 effect 会在父组件传递新的 crosshairTime 时触发
  // 即使组件被 memo，props 仍然会被传递，只是组件不重新渲染
  useEffect(() => {
    crosshairTimeRef.current = crosshairTime ?? null
    
    // 同步 crosshair 到图表
    if (crosshairTime !== undefined && !data.initialLoading && data.priceData.length > 0) {
      priceChartRef.current?.setCrosshair(crosshairTime)
      attentionChartRef.current?.setCrosshair(crosshairTime)
    }
  }, [crosshairTime, data.initialLoading, data.priceData.length])

  // 加载数据 - 使用 useCallback 封装
  // showLoading: true 表示显示 loading 状态（首次加载），false 表示静默更新
  const loadData = useCallback(async (showLoading = true) => {
    // 如果需要显示 loading，先清除错误
    if (showLoading) {
      setData(prev => ({ ...prev, error: null }))
    }

    try {
      const tradingSymbol = `${symbol}USDT`

      // 并行获取所有数据（包括 Regime 分析）
      const [priceData, attentionData, events, regimeData] = await Promise.all([
        fetchPrice({
          symbol: tradingSymbol,
          timeframe,
          start: dateRange.start,
          end: dateRange.end,
        }),
        fetchAttention({
          symbol,
          granularity: '1d',
          start: dateRange.start,
          end: dateRange.end,
        }),
        fetchAttentionEvents({
          symbol,
          start: dateRange.start,
          end: dateRange.end,
          lookback_days: 30,
          min_quantile: 0.9,
        }),
        // Regime 分析也并行加载
        fetchAttentionRegimeAnalysis({
          symbols: [symbol],
          lookahead_days: [7, 30],
          attention_source: 'composite',
          split_method: 'tercile',
        }).catch(err => {
          console.warn(`[MajorAssetModule] Failed to load regime data for ${symbol}:`, err)
          return null
        }),
      ])

      // 计算摘要统计
      const latestPrice = priceData.length > 0 ? priceData[priceData.length - 1] : null
      const previousPrice = priceData.length > 1 ? priceData[priceData.length - 2] : null
      const latestAttention = attentionData.length > 0 ? attentionData[attentionData.length - 1] : null

      const currentPrice = latestPrice?.close || 0
      const prevClose = previousPrice?.close || currentPrice
      const priceChange24h = prevClose !== 0 ? ((currentPrice - prevClose) / prevClose) * 100 : 0
      
      // 使用 composite_attention_score 和 zscore
      const currentAttention = latestAttention?.composite_attention_score || latestAttention?.attention_score || 0
      const attentionZscore = latestAttention?.composite_attention_zscore || 0

      setData({
        priceData,
        attentionData,
        events,
        regimeData,
        currentPrice,
        priceChange24h,
        currentAttention,
        attentionZscore,
        initialLoading: false,
        error: null,
      })
    } catch (err) {
      console.error(`[MajorAssetModule] Error loading data for ${symbol}:`, err)
      setData(prev => ({
        ...prev,
        initialLoading: false,
        error: err instanceof Error ? err.message : 'Failed to load data',
      }))
    }
  }, [symbol, timeframe, dateRange.start, dateRange.end])

  // 使用 ref 跟踪是否已经加载过数据
  const hasLoadedRef = useRef(false)
  const prevParamsRef = useRef<string>('')

  // 加载数据 - 首次加载或参数变化时才执行
  useEffect(() => {
    // 构建参数签名用于比较
    const currentParams = `${symbol}-${timeframe}-${dateRange.start || 'all'}-${dateRange.end || 'now'}`
    
    // 如果参数没变，不重新加载
    if (prevParamsRef.current === currentParams) {
      return
    }
    
    // 更新参数签名
    prevParamsRef.current = currentParams
    
    // 首次加载显示 loading，后续静默更新
    const isFirstLoad = !hasLoadedRef.current
    loadData(isFirstLoad) // isFirstLoad=true 显示 loading, false 静默更新
    hasLoadedRef.current = true
  }, [loadData, symbol, timeframe, dateRange.start, dateRange.end])

  // 处理图表范围同步 - 使用 useCallback 保持引用稳定
  const handlePriceRangeChange = useCallback((range: Range<Time> | null) => {
    if (range && attentionChartRef.current) {
      attentionChartRef.current.setVisibleRange(range)
    }
  }, [])

  const handleAttentionRangeChange = useCallback((range: Range<Time> | null) => {
    if (range && priceChartRef.current) {
      priceChartRef.current.setVisibleRange(range)
    }
  }, [])

  const attentionLevel = getAttentionLevel(data.attentionZscore)
  const attentionLevelColor = getAttentionLevelColor(attentionLevel)
  const isPositive = data.priceChange24h >= 0

  return (
    <Card className="bg-card/80 backdrop-blur border-border/50">
      {/* 顶部信息条 */}
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          {/* 左侧：Logo + 名称 + 价格 */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-2xl">{SYMBOL_ICONS[symbol] || '🪙'}</span>
              <span className="text-xl font-bold">{symbol}/USDT</span>
            </div>
            
            <div className="flex items-center gap-3 ml-4">
              <span className="text-2xl font-bold">${formatNumber(data.currentPrice)}</span>
              <span className={`flex items-center text-sm font-medium ${isPositive ? 'text-chart-green' : 'text-chart-red'}`}>
                {isPositive ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
                {formatPercentage(data.priceChange24h)}
              </span>
            </div>
          </div>

          {/* 右侧：Attention 状态 */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/50 rounded-lg">
              <Activity className={`w-4 h-4 ${attentionLevelColor}`} />
              <span className={`font-medium ${attentionLevelColor}`}>{attentionLevel}</span>
              <span className="text-muted-foreground text-sm">
                (z: {data.attentionZscore.toFixed(2)})
              </span>
            </div>
            <div className="text-sm text-muted-foreground">
              Attention: <span className="font-medium text-foreground">{data.currentAttention.toFixed(1)}</span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Loading 状态 - 使用骨架屏替代转圈 */}
        {data.initialLoading && (
          <div className="space-y-4 animate-pulse">
            <div className="bg-muted/50 rounded-lg h-[220px]" />
            <div className="bg-muted/50 rounded-lg h-[80px]" />
            <div className="bg-muted/50 rounded-lg h-[120px]" />
          </div>
        )}

        {data.error && (
          <div className="text-center text-red-500 py-8">
            <p>Failed to load data: {data.error}</p>
          </div>
        )}

        {!data.initialLoading && !data.error && (
          <>
            {/* 上方：价格 + 成交量图（全宽） */}
            <div className="bg-card rounded-lg border p-3">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-primary" />
                  Price & Volume
                </h4>
                <div className="flex items-center gap-1">
                  <Button
                    variant={showEventMarkers ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setShowEventMarkers(!showEventMarkers)}
                    className="text-xs h-6 px-2"
                  >
                    Events
                  </Button>
                </div>
              </div>
              <PriceChart
                ref={priceChartRef}
                priceData={data.priceData}
                height={200}
                onVisibleRangeChange={handlePriceRangeChange}
                events={data.events}
                volumeRatio={volumeRatio}
                showEventMarkers={showEventMarkers}
                onShowEventMarkersChange={setShowEventMarkers}
                onCrosshairMove={onCrosshairMove}
                hideControls={true}
              />
            </div>

            {/* 下方：Attention 曲线图（高度约为 Price 的 1/4） */}
            <div className="bg-card rounded-lg border p-3">
              <h4 className="text-sm font-medium flex items-center gap-2 mb-1">
                <BarChart3 className="w-4 h-4 text-yellow-500" />
                Attention Score
              </h4>
              <AttentionChart
                ref={attentionChartRef}
                attentionData={data.attentionData}
                height={60}
                onVisibleRangeChange={handleAttentionRangeChange}
                onCrosshairMove={onCrosshairMove}
              />
            </div>

            {/* 底部：Attention Regime Analysis 智能分析报告 */}
            <SingleSymbolRegimeAnalysis 
              symbol={symbol} 
              regimeData={data.regimeData} 
            />
          </>
        )}
      </CardContent>
    </Card>
  )
}

// 使用 React.memo 包装，优化渲染性能
// crosshairTime 变化会触发重渲染以实现图表联动
const MajorAssetModule = memo(MajorAssetModuleComponent, (prevProps, nextProps) => {
  // 返回 true 表示 props 相等，不需要重新渲染
  return (
    prevProps.symbol === nextProps.symbol &&
    prevProps.timeframe === nextProps.timeframe &&
    prevProps.dateRange.start === nextProps.dateRange.start &&
    prevProps.dateRange.end === nextProps.dateRange.end &&
    prevProps.onCrosshairMove === nextProps.onCrosshairMove &&
    prevProps.crosshairTime === nextProps.crosshairTime
  )
})

export default MajorAssetModule

/**
 * 单个代币的 Attention Regime 分析组件
 * 使用预加载的 regimeData，显示表格和智能分析报告
 */
interface SingleSymbolRegimeAnalysisProps {
  symbol: string
  regimeData: AttentionRegimeResponse | null
}

function SingleSymbolRegimeAnalysis({ symbol, regimeData }: SingleSymbolRegimeAnalysisProps) {
  const symRes = regimeData?.results?.[symbol]
  const lookaheadDays = regimeData?.meta?.lookahead_days || [7, 30]

  // regimes 可能是数组或对象，统一转换为数组
  const regimesArray = React.useMemo(() => {
    if (!symRes?.regimes) return []
    // 如果已经是数组
    if (Array.isArray(symRes.regimes)) {
      return symRes.regimes
    }
    // 如果是对象，转换为数组
    return Object.entries(symRes.regimes).map(([name, stats]) => ({
      name,
      stats
    }))
  }, [symRes?.regimes])

  // 生成智能分析报告
  const generateAnalysisReport = (regimes: any[]) => {
    if (!regimes || regimes.length < 2) return null
    
    const low = regimes[0]
    const high = regimes[regimes.length - 1]
    
    return (
      <div className="mt-3 p-3 bg-muted/50 rounded text-xs space-y-2 border border-border/50">
        <div className="font-semibold text-foreground flex items-center gap-2">
          <span>💡 智能分析报告</span>
          <span className="text-[10px] font-normal text-muted-foreground bg-background px-1.5 py-0.5 rounded border">基于历史数据统计</span>
        </div>
        {lookaheadDays.map(days => {
          const k = String(days)
          const lowStats = low.stats?.[k]
          const highStats = high.stats?.[k]
          
          if (!lowStats || !highStats) return null
          
          const lowRet = lowStats.avg_return
          const highRet = highStats.avg_return
          const diff = highRet - lowRet
          
          let conclusion = ""
          let colorClass = "text-muted-foreground"
          
          if (highRet > 0.01 && diff > 0.005) {
            conclusion = "存在显著的动量效应，高关注度往往伴随价格上涨，适合顺势交易。"
            colorClass = "text-green-500 dark:text-green-400"
          } else if (highRet < -0.01) {
            conclusion = "存在过热反转风险，高关注度后往往伴随价格回调，需警惕追高。"
            colorClass = "text-red-500 dark:text-red-400"
          } else if (highRet > 0 && diff < -0.005) {
            conclusion = "虽然平均收益为正，但不如低关注度时期（边际效用递减），性价比降低。"
            colorClass = "text-yellow-600 dark:text-yellow-400"
          } else if (Math.abs(highRet) < 0.005) {
            conclusion = "高关注度下价格波动无明显方向，可能处于震荡期。"
          } else {
            conclusion = "关注度对未来收益影响不明确，建议结合其他指标。"
          }

          return (
            <div key={k} className="flex flex-col sm:flex-row sm:gap-2">
              <span className="font-medium min-w-[60px] text-muted-foreground">{days}天展望:</span>
              <span className={colorClass}>
                高关注度下平均收益 <strong>{(highRet * 100).toFixed(2)}%</strong> (vs 低关注度 {(lowRet * 100).toFixed(2)}%)。
                {conclusion}
              </span>
            </div>
          )
        })}
      </div>
    )
  }

  if (!symRes || regimesArray.length === 0) {
    return (
      <div className="bg-muted/30 rounded-lg p-4 border border-border/50 text-center text-sm text-muted-foreground">
        <span>Attention Regime 分析数据暂无</span>
      </div>
    )
  }

  return (
    <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          Attention Regime Analysis
        </h4>
        <span className="text-xs text-muted-foreground">Lookahead: {lookaheadDays.join(', ')} days</span>
      </div>
      
      {/* Regime 表格 */}
      <div className="overflow-x-auto text-xs">
        <table className="w-full">
          <thead className="text-muted-foreground">
            <tr>
              <th className="text-left py-1 px-2">Regime</th>
              <th className="text-right py-1 px-2">样本数</th>
              {lookaheadDays.map(k => (
                <th key={k} className="text-right py-1 px-2">Avg {k}d</th>
              ))}
              {lookaheadDays.map(k => (
                <th key={`pos-${k}`} className="text-right py-1 px-2">胜率 {k}d</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {regimesArray.map((regime: any) => {
              const firstStatKey = Object.keys(regime.stats || {})[0]
              const sampleCount = firstStatKey ? regime.stats[firstStatKey]?.sample_count : 0
              
              return (
                <tr key={regime.name} className="border-t border-border/40">
                  <td className="py-1.5 px-2 font-medium">{regime.name}</td>
                  <td className="py-1.5 px-2 text-right">{sampleCount || '—'}</td>
                  {lookaheadDays.map(k => {
                    const stats = regime.stats?.[String(k)]
                    const v = stats?.avg_return != null ? (stats.avg_return * 100).toFixed(2) + '%' : '—'
                    const color = stats?.avg_return > 0 ? 'text-green-500' : stats?.avg_return < 0 ? 'text-red-500' : ''
                    return <td key={`avg-${k}`} className={`py-1.5 px-2 text-right ${color}`}>{v}</td>
                  })}
                  {lookaheadDays.map(k => {
                    const stats = regime.stats?.[String(k)]
                    const v = stats?.pos_ratio != null ? (stats.pos_ratio * 100).toFixed(1) + '%' : '—'
                    return <td key={`pos-${k}`} className="py-1.5 px-2 text-right">{v}</td>
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      
      {/* 智能分析报告 */}
      {generateAnalysisReport(regimesArray)}
    </div>
  )
}
