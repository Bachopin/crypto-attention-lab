"use client"

import { useEffect, useState } from 'react'
import { fetchNodeInfluence, NodeInfluenceItem } from '@/lib/api'

function formatPct(x: number) {
  return `${(x * 100).toFixed(2)}%`
}

export default function NodeInfluencePage() {
  const [symbol, setSymbol] = useState<string>('ZEC')
  const [minEvents, setMinEvents] = useState<number>(10)
  const [sortBy, setSortBy] = useState<'ir' | 'mean_excess_return' | 'hit_rate'>('ir')
  const [limit, setLimit] = useState<number>(100)
  const [data, setData] = useState<NodeInfluenceItem[]>([])
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string>('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const res = await fetchNodeInfluence({ symbol, min_events: minEvents, sort_by: sortBy, limit })
      setData(res)
    } catch (e: any) {
      setError(e?.message || 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="p-6 space-y-4">
      <h1 className="text-2xl font-semibold">Node Influence (Carry Factor)</h1>

      <div className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-sm">Symbol</label>
          <input className="border rounded px-2 py-1 bg-transparent" value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())} />
        </div>
        <div>
          <label className="block text-sm">Min Events</label>
          <input type="number" className="border rounded px-2 py-1 bg-transparent" value={minEvents} onChange={e => setMinEvents(Number(e.target.value) || 0)} />
        </div>
        <div>
          <label className="block text-sm">Sort By</label>
          <select className="border rounded px-2 py-1 bg-transparent" value={sortBy} onChange={e => setSortBy(e.target.value as any)}>
            <option value="ir">IR</option>
            <option value="mean_excess_return">Mean Excess Return</option>
            <option value="hit_rate">Hit Rate</option>
          </select>
        </div>
        <div>
          <label className="block text-sm">Limit</label>
          <input type="number" className="border rounded px-2 py-1 bg-transparent" value={limit} onChange={e => setLimit(Number(e.target.value) || 1)} />
        </div>
        <button className="border rounded px-3 py-1 hover:bg-neutral-800" onClick={load} disabled={loading}>Reload</button>
      </div>

      {error && <div className="text-red-500">{error}</div>}
      {loading && <div>Loading...</div>}

      {!loading && data.length > 0 && (
        <div className="overflow-auto border rounded">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-neutral-900">
                <th className="px-3 py-2 text-left">Symbol</th>
                <th className="px-3 py-2 text-left">Node</th>
                <th className="px-3 py-2 text-right">Events</th>
                <th className="px-3 py-2 text-right">Mean Excess</th>
                <th className="px-3 py-2 text-right">Hit Rate</th>
                <th className="px-3 py-2 text-right">IR</th>
                <th className="px-3 py-2 text-left">Lookahead</th>
                <th className="px-3 py-2 text-right">Lookback</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr key={`${row.symbol}-${row.node_id}-${i}`} className={i % 2 ? 'bg-neutral-950' : ''}>
                  <td className="px-3 py-2">{row.symbol}</td>
                  <td className="px-3 py-2">{row.node_id}</td>
                  <td className="px-3 py-2 text-right">{row.n_events}</td>
                  <td className="px-3 py-2 text-right">{formatPct(row.mean_excess_return)}</td>
                  <td className="px-3 py-2 text-right">{formatPct(row.hit_rate)}</td>
                  <td className="px-3 py-2 text-right">{row.ir.toFixed(3)}</td>
                  <td className="px-3 py-2">{row.lookahead}</td>
                  <td className="px-3 py-2 text-right">{row.lookback_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && data.length === 0 && (
        <div className="text-neutral-400">No data. Adjust filters and reload.</div>
      )}
    </div>
  )
}
