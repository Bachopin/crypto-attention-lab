"use client"

import React, { useEffect, useMemo, useState, useRef } from 'react'
import NewsList from '@/components/NewsList'
import type { NewsItem } from '@/lib/api'
import { fetchNews, fetchNewsCount } from '@/lib/api'
import { Newspaper } from 'lucide-react'
import { NewsSummaryCharts } from '@/components/news/NewsSummaryCharts'
import { SymbolNewsHeatTable } from '@/components/news/SymbolNewsHeatTable'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTabData } from '@/components/TabDataProvider'

export default function NewsTab({ news: initialNews }: { news: NewsItem[] }) {
  const { state, setNewsRadar, getNewsRadar, setNewsRange, setNewsSymbolFilter } = useTabData();
  
  // --- Radar State (从 context 恢复) ---
  const [newsRange, setNewsRangeLocal] = useState<'24h' | '7d' | '14d' | '30d'>(state.newsRange);
  const [newsSymbolFilter, setNewsSymbolFilterLocal] = useState<string>(state.newsSymbolFilter);
  const [radarNews, setRadarNews] = useState<NewsItem[]>([]);
  const [radarLoading, setRadarLoading] = useState(false);
  
  // 首次加载标记
  const initialLoadDone = useRef(false);

  // --- Existing List State ---
  const [sourceFilter, setSourceFilter] = useState<string>('ALL')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [allNews, setAllNews] = useState<NewsItem[]>(initialNews)
  const [loadingMore, setLoadingMore] = useState(false)
  const [pageSize, setPageSize] = useState<number>(100)
  const [totalItems, setTotalItems] = useState<number>(initialNews.length)
  const [currentBefore, setCurrentBefore] = useState<string | null>(null)

  // --- Fetch Radar Data (带缓存) ---
  useEffect(() => {
    const fetchRadarData = async () => {
      // 检查缓存
      const cached = getNewsRadar(newsRange);
      if (cached && cached.length > 0) {
        setRadarNews(cached);
        initialLoadDone.current = true;
        return;
      }
      
      setRadarLoading(true);
      try {
        const now = new Date();
        let start = new Date();
        if (newsRange === '24h') {
          start.setHours(now.getHours() - 24);
        } else if (newsRange === '7d') {
          start.setDate(now.getDate() - 7);
          start.setHours(0, 0, 0, 0); // Align to start of day for cleaner charts
        } else if (newsRange === '14d') {
          start.setDate(now.getDate() - 14);
          start.setHours(0, 0, 0, 0); // Align to start of day
        } else if (newsRange === '30d') {
          start.setDate(now.getDate() - 30);
          start.setHours(0, 0, 0, 0); // Align to start of day
        }

        // 初始加载限制为 500 条，足够显示雷达图
        const data = await fetchNews({ 
          symbol: 'ALL', 
          start: start.toISOString(), 
          limit: 500 
        });
        setRadarNews(data);
        // 存入缓存
        setNewsRadar(data, newsRange);
        initialLoadDone.current = true;
      } catch (e) {
        console.error("Failed to fetch radar news", e);
      } finally {
        setRadarLoading(false);
      }
    };
    fetchRadarData();
  }, [newsRange, getNewsRadar, setNewsRadar]);
  
  // 同步 range 和 filter 到 context
  const handleRangeChange = (v: '24h' | '7d' | '14d' | '30d') => {
    setNewsRangeLocal(v);
    setNewsRange(v);
  };
  
  const handleSymbolFilterChange = (symbol: string) => {
    setNewsSymbolFilterLocal(symbol);
    setNewsSymbolFilter(symbol);
  };

  // --- Sync List with Radar Selection ---
  useEffect(() => {
    const now = new Date();
    let start = new Date();
    if (newsRange === '24h') {
      start.setHours(now.getHours() - 24);
    } else if (newsRange === '7d') {
      start.setDate(now.getDate() - 7);
      start.setHours(0, 0, 0, 0);
    } else if (newsRange === '14d') {
      start.setDate(now.getDate() - 14);
      start.setHours(0, 0, 0, 0);
    } else if (newsRange === '30d') {
      start.setDate(now.getDate() - 30);
      start.setHours(0, 0, 0, 0);
    }
    
    setStartDate(start.toISOString().split('T')[0]);
    setEndDate(now.toISOString().split('T')[0]);
  }, [newsRange]);

  // --- Existing List Logic ---
  const sources = useMemo(() => {
    const set = new Set<string>()
    const sourceData = radarNews.length > 0 ? radarNews : allNews;
    sourceData.forEach(n => { if (n.source) set.add(n.source) })
    return ['ALL', ...Array.from(set).sort()]
  }, [radarNews, allNews])

  const filteredNews = useMemo(() => {
    return allNews.filter(n => {
      const bySource = sourceFilter === 'ALL' ? true : (n.source === sourceFilter)
      const ts = new Date(n.datetime).getTime()
      const startTs = startDate ? new Date(`${startDate}T00:00:00`).getTime() : 0
      const endTs = endDate ? new Date(`${endDate}T23:59:59.999`).getTime() : Number.POSITIVE_INFINITY
      
      const byStart = startDate ? ts >= startTs : true
      const byEnd = endDate ? ts <= endTs : true
      
      return bySource && byStart && byEnd
    })
  }, [allNews, sourceFilter, startDate, endDate])

  // Refetch list when symbol filter or date range changes
  useEffect(() => {
    const fetchList = async () => {
      setLoadingMore(true);
      try {
        const symbolParam = newsSymbolFilter === 'ALL' ? 'ALL' : newsSymbolFilter;
        
        const res = await fetchNews({ 
          symbol: symbolParam, 
          start: startDate ? `${startDate}T00:00:00` : undefined,
          end: endDate ? `${endDate}T23:59:59` : undefined,
          limit: pageSize,
          source: sourceFilter === 'ALL' ? undefined : sourceFilter
        });
        setAllNews(res);
        
        const countRes = await fetchNewsCount({ 
          symbol: symbolParam, 
          start: startDate ? `${startDate}T00:00:00` : undefined,
          end: endDate ? `${endDate}T23:59:59` : undefined,
          source: sourceFilter === 'ALL' ? undefined : sourceFilter
        });
        setTotalItems(countRes.total);
        setCurrentBefore(null);
      } catch (e) {
        console.error("Failed to fetch list", e);
      } finally {
        setLoadingMore(false);
      }
    };
    
    fetchList();
  }, [newsSymbolFilter, startDate, endDate, sourceFilter, pageSize]);

  const loadMore = async () => {
    if (loadingMore || allNews.length === 0) return
    setLoadingMore(true)
    try {
      // 计算最早的新闻时间戳，过滤掉无效日期
      const validTimestamps = allNews
        .map(n => new Date(n.datetime).getTime())
        .filter(t => !isNaN(t) && t > 0);
      
      if (validTimestamps.length === 0) {
        console.warn('No valid timestamps found in news list');
        setLoadingMore(false);
        return;
      }
      
      const oldest = Math.min(...validTimestamps);
      const beforeCursor = currentBefore || new Date(oldest - 1).toISOString();
      
      const symbolParam = newsSymbolFilter === 'ALL' ? 'ALL' : newsSymbolFilter;

      const older = await fetchNews({ 
        symbol: symbolParam, 
        before: beforeCursor, 
        limit: pageSize, 
        source: sourceFilter === 'ALL' ? undefined : sourceFilter, 
        start: startDate ? `${startDate}T00:00:00` : undefined, 
        end: endDate ? `${endDate}T23:59:59` : undefined 
      })
      
      if (older && older.length) {
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
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Newspaper className="w-6 h-6 text-primary" />
          News & Attention Radar
        </h2>
        
        <div className="flex items-center gap-2">
           <span className="text-sm text-muted-foreground">Range:</span>
           <Select value={newsRange} onValueChange={(v: any) => handleRangeChange(v)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="24h">24 Hours</SelectItem>
              <SelectItem value="7d">7 Days</SelectItem>
              <SelectItem value="14d">14 Days</SelectItem>
              <SelectItem value="30d">30 Days</SelectItem>
            </SelectContent>
           </Select>
        </div>
      </div>

      {/* Radar Section */}
      <div className="space-y-6">
        {radarLoading ? (
           <div className="space-y-4">
             <div className="h-[120px] bg-muted/50 rounded-lg animate-pulse" />
             <div className="h-[200px] bg-muted/50 rounded-lg animate-pulse" />
           </div>
        ) : (
           <>
             <NewsSummaryCharts news={radarNews} timeRange={newsRange} />
             <SymbolNewsHeatTable 
                news={radarNews} 
                selectedSymbol={newsSymbolFilter} 
                onSymbolSelect={handleSymbolFilterChange} 
             />
           </>
        )}
      </div>

      {/* List Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
           <h3 className="text-lg font-semibold flex items-center gap-2">
             News List
             {newsSymbolFilter !== 'ALL' && <span className="text-sm font-normal bg-primary/10 text-primary px-2 py-0.5 rounded">Filtered by: {newsSymbolFilter}</span>}
           </h3>
        </div>

        {/* Filters */}
        <div className="bg-card border border-border rounded-lg p-4 flex flex-wrap items-end gap-4">
           <div className="flex-1 min-w-[200px]">
            <label className="block text-sm text-muted-foreground mb-1">Source</label>
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
            <label className="block text-sm text-muted-foreground mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="px-3 py-2 border rounded-md bg-card text-foreground border-border"
            />
          </div>

          <div>
            <label className="block text-sm text-muted-foreground mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="px-3 py-2 border rounded-md bg-card text-foreground border-border"
            />
          </div>
          
           <div>
            <label className="block text-sm text-muted-foreground mb-1">Page Size</label>
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              className="px-3 py-2 border rounded-md bg-card text-foreground border-border"
            >
              {[50, 100, 200].map(sz => (<option key={sz} value={sz}>{sz}</option>))}
            </select>
          </div>

          <button
            onClick={() => { setSourceFilter('ALL'); setNewsSymbolFilter('ALL'); }}
            className="px-3 py-2 rounded-md bg-muted text-foreground border border-border"
          >
            Reset
          </button>
        </div>

        <NewsList news={filteredNews} maxItems={filteredNews.length} title={newsSymbolFilter !== 'ALL' ? `News for ${newsSymbolFilter}` : "All News"} />

        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>Showing: {filteredNews.length} (Total {totalItems})</span>
          <button
            onClick={loadMore}
            className="px-3 py-2 rounded-md bg-muted text-foreground border border-border"
            disabled={loadingMore}
          >
            {loadingMore ? 'Loading...' : 'Load More'}
          </button>
        </div>
      </div>
    </section>
  )
}
