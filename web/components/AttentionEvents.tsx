"use client";

import React, { useEffect, useState } from 'react'
import type { AttentionEvent } from '@/lib/api'
import { fetchAttentionEventPerformance, type EventPerformanceTable } from '@/lib/api'

export default function AttentionEvents({ events }: { events: AttentionEvent[] }) {
  const [perf, setPerf] = useState<EventPerformanceTable | null>(null)

  useEffect(() => {
    fetchAttentionEventPerformance({ symbol: 'ZEC' }).then(setPerf).catch(() => setPerf(null))
  }, [])

  if (!events || events.length === 0) {
    return (
      <div className="bg-card rounded-lg border p-4 text-sm text-muted-foreground">
        No attention events detected in range.
      </div>
    );
  }

  const eventTypes = Object.keys(perf || {})
  const horizons = eventTypes.length > 0 ? Object.keys(perf![eventTypes[0]]) : []

  return (
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <div>
        <h3 className="text-lg font-semibold mb-3">Attention Events</h3>
        <div className="space-y-2 max-h-64 overflow-auto pr-1">
          {events.map((e, idx) => (
            <div key={idx} className="flex items-start gap-3 border-b border-border/50 pb-2 last:border-b-0">
              <div className="mt-1 w-2 h-2 rounded-full bg-yellow-500" />
              <div className="flex-1">
                <div className="text-sm text-muted-foreground">{new Date(e.datetime).toLocaleString()}</div>
                <div className="text-sm"><span className="font-medium">{e.event_type}</span> · intensity {e.intensity.toFixed(2)}</div>
                <div className="text-xs text-muted-foreground">{e.summary}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {perf && eventTypes.length > 0 && (
        <div className="text-xs">
          <h4 className="font-semibold mb-2">Event Forward Returns (Exp)</h4>
          <div className="overflow-auto">
            <table className="w-full border-collapse">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="text-left py-1 pr-2">Event Type</th>
                  {horizons.map(h => (
                    <th key={h} className="text-right py-1 px-2">+{h}d</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {eventTypes.map(et => (
                  <tr key={et} className="border-t border-border/40">
                    <td className="py-1 pr-2 font-medium">{et}</td>
                    {horizons.map(h => {
                      const cell = perf[et]?.[h]
                      if (!cell || cell.sample_size === 0) {
                        return <td key={h} className="text-right py-1 px-2 text-muted-foreground/60">-</td>
                      }
                      return (
                        <td key={h} className="text-right py-1 px-2">
                          {(cell.avg_return * 100).toFixed(2)}%
                          <span className="ml-1 text-[10px] text-muted-foreground">(n={cell.sample_size})</span>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

