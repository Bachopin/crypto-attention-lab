"use client";

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import type { BacktestResult } from '@/lib/api';
import { runBasicAttentionBacktest } from '@/lib/api';

export default function BacktestPanel() {
  const [params, setParams] = useState({
    symbol: 'ZECUSDT',
    lookback_days: 30,
    attention_quantile: 0.8,
    max_daily_return: 0.05,
    holding_days: 3,
  });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true); setError(null);
    try {
      const res = await runBasicAttentionBacktest(params);
      setResult(res);
    } catch (e: any) {
      setError(e?.message || 'Backtest failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <h3 className="text-lg font-semibold">Basic Attention Strategy</h3>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        <label className="flex flex-col gap-1 group cursor-help">
          <span className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" title="回看天数：用于计算注意力分位数的历史窗口长度（例如30天）。">
            Lookback Days
          </span>
          <input className="px-2 py-1 bg-background border rounded" type="number" value={params.lookback_days}
                 onChange={e => setParams(p => ({...p, lookback_days: Number(e.target.value)}))}/>
        </label>
        <label className="flex flex-col gap-1 group cursor-help">
          <span className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" title="注意力阈值（分位数）：触发买入信号的强度标准。例如0.8代表当前注意力超过过去80%的时间。">
            Threshold (Quantile)
          </span>
          <input className="px-2 py-1 bg-background border rounded" type="number" step="0.05" min={0} max={1}
                 value={params.attention_quantile}
                 onChange={e => setParams(p => ({...p, attention_quantile: Number(e.target.value)}))}/>
        </label>
        <label className="flex flex-col gap-1 group cursor-help">
          <span className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" title="最大日涨幅限制：如果当日涨幅超过此值（例如0.05即5%），则不追高买入，防止高位接盘。">
            Max Daily Return
          </span>
          <input className="px-2 py-1 bg-background border rounded" type="number" step="0.01"
                 value={params.max_daily_return}
                 onChange={e => setParams(p => ({...p, max_daily_return: Number(e.target.value)}))}/>
        </label>
        <label className="flex flex-col gap-1 group cursor-help">
          <span className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" title="持仓天数：信号触发后，默认持有的交易日数量。">
            Holding Period
          </span>
          <input className="px-2 py-1 bg-background border rounded" type="number"
                 value={params.holding_days}
                 onChange={e => setParams(p => ({...p, holding_days: Number(e.target.value)}))}/>
        </label>
        <div className="flex items-end"><Button onClick={run} disabled={loading}>{loading ? 'Running...' : 'Run Backtest'}</Button></div>
      </div>

      {error && <div className="text-red-500 text-sm">{error}</div>}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
            <Stat label="Trades" value={result.summary.total_trades} />
            <Stat label="Win Rate" value={`${result.summary.win_rate.toFixed(1)}%`} />
            <Stat label="Avg Return" value={`${(result.summary.avg_return*100).toFixed(2)}%`} />
            <Stat label="Cumulative" value={`${(result.summary.cumulative_return*100).toFixed(2)}%`} />
            <Stat label="Max DD" value={`${(result.summary.max_drawdown*100).toFixed(2)}%`} />
          </div>

          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="text-left py-2">Entry</th>
                  <th className="text-left py-2">Exit</th>
                  <th className="text-right py-2">Entry Px</th>
                  <th className="text-right py-2">Exit Px</th>
                  <th className="text-right py-2">Return</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.map((t, i) => (
                  <tr key={i} className="border-t border-border/50">
                    <td className="py-1">{new Date(t.entry_date).toLocaleDateString()}</td>
                    <td className="py-1">{new Date(t.exit_date).toLocaleDateString()}</td>
                    <td className="text-right">{t.entry_price.toFixed(2)}</td>
                    <td className="text-right">{t.exit_price.toFixed(2)}</td>
                    <td className="text-right">{(t.return_pct*100).toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
