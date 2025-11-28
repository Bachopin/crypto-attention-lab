"use client";

import React, { useState, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import type { AttentionRotationResult, EquityPoint } from '@/lib/api';
import { runAttentionRotationBacktest } from '@/lib/api';

type AttentionSource = 'composite' | 'news_channel';

interface RotationParams {
  symbols: string; // Comma separated string for input
  attention_source: AttentionSource;
  rebalance_days: number;
  lookback_days: number;
  top_k: number;
}

export default function AttentionRotationPanel() {
  const [params, setParams] = useState<RotationParams>({
    symbols: 'ZECUSDT,BTCUSDT,ETHUSDT,SOLUSDT',
    attention_source: 'composite',
    rebalance_days: 7,
    lookback_days: 30,
    top_k: 2,
  });
  const [result, setResult] = useState<AttentionRotationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const symbolList = params.symbols.split(',').map(s => s.trim()).filter(s => s);
      if (symbolList.length === 0) throw new Error("Please provide at least one symbol");

      const res = await runAttentionRotationBacktest({
        symbols: symbolList,
        attention_source: params.attention_source,
        rebalance_days: params.rebalance_days,
        lookback_days: params.lookback_days,
        top_k: params.top_k,
      });
      setResult(res);
    } catch (e: any) {
      setError(e?.message || 'Backtest failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <h3 className="text-lg font-semibold">Attention Rotation Strategy</h3>
      <div className="text-xs text-muted-foreground">
        定期根据 Attention 指标选择前 K 个币持有，形成简单的 rotation 策略。
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
        <div className="col-span-1 md:col-span-2">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Symbol Pool (comma separated)</span>
            <input
              className="px-2 py-1 bg-background border rounded w-full"
              value={params.symbols}
              onChange={e => setParams(p => ({ ...p, symbols: e.target.value }))}
            />
          </label>
        </div>
        
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Rebalance Days</span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            min={1}
            value={params.rebalance_days}
            onChange={e => setParams(p => ({ ...p, rebalance_days: Number(e.target.value) }))}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Lookback Days</span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            min={1}
            value={params.lookback_days}
            onChange={e => setParams(p => ({ ...p, lookback_days: Number(e.target.value) }))}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Top K</span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            min={1}
            value={params.top_k}
            onChange={e => setParams(p => ({ ...p, top_k: Number(e.target.value) }))}
          />
        </label>

        <div className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Attention Source</span>
          <div className="flex gap-2">
            {([
              { key: 'composite', label: 'Composite' },
              { key: 'news_channel', label: 'News Only' },
            ] as { key: AttentionSource; label: string }[]).map(option => (
              <button
                key={option.key}
                type="button"
                onClick={() => setParams(p => ({ ...p, attention_source: option.key }))}
                className={`rounded border px-3 py-1 text-xs ${
                  params.attention_source === option.key
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-background hover:bg-muted'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <Button onClick={run} disabled={loading} className="w-full md:w-auto">
        {loading ? 'Running Backtest...' : 'Run Rotation Backtest'}
      </Button>

      {error && <div className="text-red-500 text-sm">{error}</div>}

      {result && (
        <div className="space-y-4 mt-4 border-t pt-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <Stat label="Total Return" value={`${(result.summary.total_return * 100).toFixed(2)}%`} />
            <Stat label="Annualized" value={`${(result.summary.annualized_return * 100).toFixed(2)}%`} />
            <Stat label="Max Drawdown" value={`${(result.summary.max_drawdown * 100).toFixed(2)}%`} />
            <Stat label="Sharpe" value={result.summary.sharpe.toFixed(2)} />
          </div>

          {result.equity_curve && result.equity_curve.length > 0 && (
            <EquityCurve
              title="Portfolio Equity Curve"
              points={result.equity_curve}
            />
          )}

          <div className="space-y-2">
            <h4 className="text-sm font-medium">Rebalance Log (Last 10)</h4>
            <div className="overflow-auto max-h-60 border rounded">
              <table className="w-full text-xs">
                <thead className="bg-muted/50 text-muted-foreground sticky top-0">
                  <tr>
                    <th className="text-left py-2 px-2">Date</th>
                    <th className="text-left py-2 px-2">Selected Symbols</th>
                    <th className="text-left py-2 px-2">Scores</th>
                  </tr>
                </thead>
                <tbody>
                  {[...result.rebalance_log].reverse().slice(0, 10).map((log, i) => (
                    <tr key={i} className="border-t border-border/50">
                      <td className="py-1 px-2 whitespace-nowrap">{new Date(log.rebalance_date).toLocaleDateString()}</td>
                      <td className="py-1 px-2">
                        <div className="flex flex-wrap gap-1">
                          {log.selected_symbols.map(s => (
                            <span key={s} className="bg-primary/10 text-primary px-1 rounded">{s}</span>
                          ))}
                        </div>
                      </td>
                      <td className="py-1 px-2 text-muted-foreground">
                        {log.selected_symbols.map(s => `${s}: ${log.attention_values[s]?.toFixed(1)}`).join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="bg-background rounded border p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-base font-semibold">{value}</div>
    </div>
  )
}

function EquityCurve({ title, points }: { title: string; points: EquityPoint[] }) {
  const { path, minEquity, maxEquity } = useMemo(() => {
    if (!points.length) return { path: '', minEquity: 0, maxEquity: 0 };
    const values = points.map(p => p.equity);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const width = 100;
    const height = 40;
    const stepX = points.length > 1 ? width / (points.length - 1) : 0;
    const d = points
      .map((p, idx) => {
        const x = idx * stepX;
        const y = height - ((p.equity - min) / span) * height;
        return `${idx === 0 ? 'M' : 'L'}${x},${y}`;
      })
      .join(' ');
    return { path: d, minEquity: min, maxEquity: max };
  }, [points]);

  if (!points.length || !path) return null;

  return (
    <div className="space-y-1 rounded border bg-background p-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{title}</span>
        <span>{`区间权益：${minEquity.toFixed(2)} → ${maxEquity.toFixed(2)}`}</span>
      </div>
      <svg viewBox="0 0 100 40" className="h-24 w-full">
        <path d={path} fill="none" strokeWidth={1.5} className="stroke-primary" />
      </svg>
    </div>
  );
}
