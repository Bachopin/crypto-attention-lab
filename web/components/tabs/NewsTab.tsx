"use client"

import React, { useEffect, useMemo, useState } from 'react'
import NewsList from '@/components/NewsList'
import type { NewsItem } from '@/lib/api'
import { fetchNews, fetchNewsCount } from '@/lib/api'
import { Newspaper } from 'lucide-react'
import { NewsSummaryCharts } from '@/components/news/NewsSummaryCharts'
import { SymbolNewsHeatTable } from '@/components/news/SymbolNewsHeatTable'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export default function NewsTab({ news: initialNews }: { news: NewsItem[] }) {
  // --- Radar State ---
  const [newsRange, setNewsRange] = useState<'24h' | '7d' | '30d'>('7d');
  const [newsSymbolFilter, setNewsSymbolFilter] = useState<string>('ALL');
  const [radarNews, setRadarNews] = useState<NewsItem[]>([]);
  const [radarLoading, setRadarLoading] = useState(false);

  // --- Existing List State ---
  const [sourceFilter, setSourceFilter] = useState<string>('ALL')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [allNews, setAllNews] = useState<NewsItem[]>(initialNews)
  const [loadingMore, setLoadingMore] = useState(false)
  const [pageSize, setPageSize] = useState<number>(100)
  const [totalItems, setTotalItems] = useState<number>(initialNews.length)
  const [currentBefore, setCurrentBefore] = useState<string | null>(null)

  // --- Fetch Radar Data ---
  useEffect(() => {
    const fetchRadarData = async () => {
      setRadarLoading(true);
      try {
        const now = new Date();
        let start = new Date();
        if (newsRange === '24h') {
          start.setHours(now.getHours() - 24);
        } else if (newsRange === '7d') {
          start.setDate(now.getDate() - 7);
          start.setHours(0, 0, 0, 0); // Align to start of day for cleaner charts
        } else if (newsRange === '30d') {
          start.setDate(now.getDate() - 30);
          start.setHours(0, 0, 0, 0); // Align to start of day
        }

        // Fetch ALL news for the range to build the radar
        // Limit to 5000 to ensure we cover the full range without truncation
        const data = await fetchNews({ 
          symbol: 'ALL', 
          start: start.toISOString(), 
          limit: 5000 
        });
        setRadarNews(data);
      } catch (e) {
        console.error("Failed to fetch radar news", e);
      } finally {
        setRadarLoading(false);
      }
    };
    fetchRadarData();
  }, [newsRange]);

  // --- Sync List with Radar Selection ---
  useEffect(() => {
    const now = new Date();
    let start = new Date();
    if (newsRange === '24h') {
      start.setHours(now.getHours() - 24);
    } else if (newsRange === '7d') {
      start.setDate(now.getDate() - 7);
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
      const oldest = allNews.reduce((min, n) => Math.min(min, new Date(n.datetime).getTime()), Number.POSITIVE_INFINITY)
      const beforeCursor = (currentBefore ? currentBefore : new Date(oldest - 1).toISOString())
      
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
           <Select value={newsRange} onValueChange={(v: any) => setNewsRange(v)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue placeholder="Range" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="24h">24 Hours</SelectItem>
              <SelectItem value="7d">7 Days</SelectItem>
              <SelectItem value="30d">30 Days</SelectItem>
            </SelectContent>
           </Select>
        </div>
      </div>

      {/* Radar Section */}
      <div className="space-y-6">
        {radarLoading ? (
           <div className="h-[200px] flex items-center justify-center border rounded-lg bg-card text-muted-foreground">
             Loading Radar Data...
           </div>
        ) : (
           <>
             <NewsSummaryCharts news={radarNews} timeRange={newsRange} />
             <SymbolNewsHeatTable 
                news={radarNews} 
                selectedSymbol={newsSymbolFilter} 
                onSymbolSelect={setNewsSymbolFilter} 
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
