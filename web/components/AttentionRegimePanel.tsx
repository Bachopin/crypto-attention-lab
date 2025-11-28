"use client";

import React, { useState } from 'react';
import { fetchAttentionRegimeAnalysis, AttentionRegimeResponse } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface Props {
  defaultSymbols?: string[];
}

export default function AttentionRegimePanel({ defaultSymbols = ['ZEC','BTC','ETH'] }: Props) {
  const [symbolsInput, setSymbolsInput] = useState(defaultSymbols.join(','));
  const [lookaheadDaysInput, setLookaheadDaysInput] = useState('7,30');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AttentionRegimeResponse | null>(null);
  const [attentionSource, setAttentionSource] = useState<'composite' | 'news_channel'>('composite');
  const [splitMethod, setSplitMethod] = useState<'tercile' | 'quartile'>('tercile');

  async function runAnalysis() {
    setLoading(true); setError(null); setData(null);
    try {
      const symbols = symbolsInput.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
      const lookahead_days = lookaheadDaysInput.split(',').map(s => Number(s.trim())).filter(v => !isNaN(v) && v > 0);
      if (!symbols.length) throw new Error('请提供至少一个 symbol');
      const res = await fetchAttentionRegimeAnalysis({ symbols, lookahead_days, attention_source: attentionSource, split_method: splitMethod });
      setData(res);
    } catch (e: any) {
      setError(e?.message || '分析失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <h3 className="text-lg font-semibold">Attention Regime Analysis</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Symbols (逗号分隔)</span>
          <input className="px-2 py-1 bg-background border rounded" value={symbolsInput} onChange={e => setSymbolsInput(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Lookahead Days</span>
          <input className="px-2 py-1 bg-background border rounded" value={lookaheadDaysInput} onChange={e => setLookaheadDaysInput(e.target.value)} />
        </label>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Attention Source</span>
          <div className="flex gap-2">
            {(['composite','news_channel'] as const).map(src => (
              <button key={src} type="button" onClick={() => setAttentionSource(src)} className={`rounded border px-2 py-1 text-xs ${attentionSource === src ? 'bg-primary text-primary-foreground' : 'bg-background hover:bg-muted'}`}>{src}</button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Split Method</span>
          <div className="flex gap-2">
            {(['tercile','quartile'] as const).map(m => (
              <button key={m} type="button" onClick={() => setSplitMethod(m)} className={`rounded border px-2 py-1 text-xs ${splitMethod === m ? 'bg-primary text-primary-foreground' : 'bg-background hover:bg-muted'}`}>{m}</button>
            ))}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button onClick={runAnalysis} disabled={loading}>{loading ? 'Running...' : 'Run Analysis'}</Button>
        {error && <div className="text-red-500 text-xs">{error}</div>}
      </div>

      {data && (
        <div className="overflow-auto text-xs">
          {Object.entries(data.results).map(([sym, symRes]: [string, any]) => (
            <div key={sym} className="mb-4 rounded border bg-background p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-medium">{sym}</span>
                {symRes.meta?.error && <span className="text-red-500">{symRes.meta.error}</span>}
              </div>
              <table className="w-full">
                <thead className="text-muted-foreground">
                  <tr>
                    <th className="text-left py-1">Regime</th>
                    <th className="text-right py-1">Samples</th>
                    {data.meta.lookahead_days.map(k => (
                      <th key={k} className="text-right py-1">Avg {k}d</th>
                    ))}
                    {data.meta.lookahead_days.map(k => (
                      <th key={`pos-${k}`} className="text-right py-1">Pos {k}d</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {symRes.regimes && symRes.regimes.map((regime: any) => {
                    // Get sample count from the first available stats
                    const firstStatKey = Object.keys(regime.stats)[0];
                    const sampleCount = firstStatKey ? regime.stats[firstStatKey].sample_count : 0;
                    
                    return (
                      <tr key={regime.name} className="border-t border-border/40">
                        <td className="py-1 font-medium">{regime.name}</td>
                        <td className="py-1 text-right">{sampleCount}</td>
                        {data.meta.lookahead_days.map(k => {
                          const stats = regime.stats[String(k)];
                          const v = stats?.avg_return != null ? (stats.avg_return * 100).toFixed(2) + '%' : '-';
                          return <td key={`avg-${k}`} className="py-1 text-right">{v}</td>;
                        })}
                        {data.meta.lookahead_days.map(k => {
                          const stats = regime.stats[String(k)];
                          const v = stats?.pos_ratio != null ? (stats.pos_ratio * 100).toFixed(1) + '%' : '-';
                          return <td key={`pos-${k}`} className="py-1 text-right">{v}</td>;
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}