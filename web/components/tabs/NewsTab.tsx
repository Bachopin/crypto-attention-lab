"use client"

import React, { useEffect, useMemo, useState } from 'react'
import NewsList from '@/components/NewsList'
import type { NewsItem } from '@/lib/api'
import { fetchNews, fetchNewsCount } from '@/lib/api'
import { Newspaper } from 'lucide-react'

export default function NewsTab({ news }: { news: NewsItem[] }) {
  const [sourceFilter, setSourceFilter] = useState<string>('ALL')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [allNews, setAllNews] = useState<NewsItem[]>(news)
  const [loadingMore, setLoadingMore] = useState(false)
  const [pageSize, setPageSize] = useState<number>(100)
  const [totalItems, setTotalItems] = useState<number>(news.length)
  const [currentBefore, setCurrentBefore] = useState<string | null>(null)

  const sources = useMemo(() => {
    const set = new Set<string>()
    news.forEach(n => { if (n.source) set.add(n.source) })
    return ['ALL', ...Array.from(set).sort()]
  }, [news])

  const filteredNews = useMemo(() => {
    return allNews.filter(n => {
      const bySource = sourceFilter === 'ALL' ? true : (n.source === sourceFilter)
      const ts = new Date(n.datetime).getTime()
      // Use local time for start/end date comparison
      const startTs = startDate ? new Date(`${startDate}T00:00:00`).getTime() : 0
      const endTs = endDate ? new Date(`${endDate}T23:59:59.999`).getTime() : Number.POSITIVE_INFINITY
      
      const byStart = startDate ? ts >= startTs : true
      const byEnd = endDate ? ts <= endTs : true
      return bySource && byStart && byEnd
    })
  }, [allNews, sourceFilter, startDate, endDate])

  // 依据筛选计算总数（后端统计），并重置分页游标
  useEffect(() => {
    const updateTotal = async () => {
      try {
        const res = await fetchNewsCount({ symbol: 'ALL', source: sourceFilter === 'ALL' ? undefined : sourceFilter, start: startDate || undefined, end: endDate || undefined })
        setTotalItems(res.total)
        setCurrentBefore(null)
      } catch (e) {
        console.error('[NewsTab] fetchNewsCount failed:', e)
      }
    }
    updateTotal()
  }, [sourceFilter, startDate, endDate])

  // 向后加载更旧的新闻（按当前已有的最旧时间再向前取一段）
  const loadMore = async () => {
    if (loadingMore || allNews.length === 0) return
    setLoadingMore(true)
    try {
      const oldest = allNews.reduce((min, n) => Math.min(min, new Date(n.datetime).getTime()), Number.POSITIVE_INFINITY)
      const beforeCursor = (currentBefore ? currentBefore : new Date(oldest - 1).toISOString())
      const older = await fetchNews({ symbol: 'ALL', before: beforeCursor, limit: pageSize, source: sourceFilter === 'ALL' ? undefined : sourceFilter, start: startDate || undefined, end: endDate || undefined })
      if (older && older.length) {
        // 合并后去重（按 url 作为唯一键）
        const map = new Map<string, NewsItem>()
        const combined = allNews.concat(older)
        for (const n of combined) {
          if (n.url) {
            map.set(n.url, n)
          }
        }
        setAllNews(Array.from(map.values()))
        const newOldest = (older.reduce((min, n) => Math.min(min, new Date(n.datetime).getTime()), Number.POSITIVE_INFINITY))
        setCurrentBefore(new Date(newOldest - 1).toISOString())
      }
    } catch (e) {
      console.error('[NewsTab] loadMore failed:', e)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <section className="space-y-4">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <Newspaper className="w-6 h-6 text-primary" />
        新闻概览
      </h2>

      {/* Filters */}
      <div className="bg-card border border-border rounded-lg p-4 flex flex-wrap items-end gap-4">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm text-muted-foreground mb-1">新闻源</label>
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="w-full px-3 py-2 border rounded-md bg-card text-foreground border-border"
          >
            {sources.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm text-muted-foreground mb-1">开始日期</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="px-3 py-2 border rounded-md bg-card text-foreground border-border"
          />
        </div>

        <div>
          <label className="block text-sm text-muted-foreground mb-1">结束日期</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="px-3 py-2 border rounded-md bg-card text-foreground border-border"
          />
        </div>

        <div>
          <label className="block text-sm text-muted-foreground mb-1">每页条数</label>
          <select
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
            className="px-3 py-2 border rounded-md bg-card text-foreground border-border"
          >
            {[50, 100, 200].map(sz => (<option key={sz} value={sz}>{sz}</option>))}
          </select>
        </div>

        <button
          onClick={() => { setSourceFilter('ALL'); setStartDate(''); setEndDate(''); }}
          className="px-3 py-2 rounded-md bg-muted text-foreground border border-border"
        >
          重置
        </button>
      </div>

      <NewsList news={filteredNews} maxItems={filteredNews.length} title="筛选后的新闻" />

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>当前显示：{filteredNews.length} 条（总计 {totalItems} 条，约 {Math.ceil((totalItems || 0) / pageSize)} 页）</span>
        <button
          onClick={loadMore}
          className="px-3 py-2 rounded-md bg-muted text-foreground border border-border"
          disabled={loadingMore}
        >
          {loadingMore ? '加载中…' : '加载更多'}
        </button>
      </div>
    </section>
  )
}
