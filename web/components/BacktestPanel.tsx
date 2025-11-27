"use client";

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import type { BacktestResult, BacktestSummary, MultiBacktestResult, EquityPoint } from '@/lib/api';
import { runBasicAttentionBacktest, runMultiSymbolBacktest } from '@/lib/api';

export default function BacktestPanel() {
  const [params, setParams] = useState({
    symbol: 'ZECUSDT',
    lookback_days: 30,
    attention_quantile: 0.8,
    max_daily_return: 0.05,
    holding_days: 3,
    stop_loss_pct: 0.05 as number | null,
    take_profit_pct: 0.1 as number | null,
    max_holding_days: 5 as number | null,
    position_size: 1.0,
  });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [multiResult, setMultiResult] = useState<MultiBacktestResult | null>(null);
  const [selectedMultiSymbol, setSelectedMultiSymbol] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [presetName, setPresetName] = useState('default');
  const [availablePresets, setAvailablePresets] = useState<string[]>([]);
  const [strategySummaries, setStrategySummaries] = useState<Record<string, BacktestSummary>>({});
  const [strategyEquities, setStrategyEquities] = useState<Record<string, EquityPoint[]>>({});
  const [selectedComparePresets, setSelectedComparePresets] = useState<string[]>([]);

  const PRESET_PREFIX = 'basic-attention-preset-';
  const SUMMARY_PREFIX = 'basic-attention-summary-';
  const EQUITY_PREFIX = 'basic-attention-equity-';

  const loadPresetKeysAndData = useCallback(() => {
    if (typeof window === 'undefined') return;
    try {
      const keys: string[] = [];
      const summaries: Record<string, BacktestSummary> = {};
      const equities: Record<string, EquityPoint[]> = {};
      for (let i = 0; i < window.localStorage.length; i++) {
        const key = window.localStorage.key(i);
        if (key && key.startsWith(PRESET_PREFIX)) {
          const name = key.replace(PRESET_PREFIX, '');
          keys.push(name);

          const summaryRaw = window.localStorage.getItem(`${SUMMARY_PREFIX}${name}`);
          if (summaryRaw) {
            try {
              summaries[name] = JSON.parse(summaryRaw) as BacktestSummary;
            } catch (e) {
              console.warn('Failed to parse summary for preset', name, e);
            }
          }

          const equityRaw = window.localStorage.getItem(`${EQUITY_PREFIX}${name}`);
          if (equityRaw) {
            try {
              equities[name] = JSON.parse(equityRaw) as EquityPoint[];
            } catch (e) {
              console.warn('Failed to parse equity for preset', name, e);
            }
          }
        }
      }
      keys.sort();
      setAvailablePresets(keys);
      setStrategySummaries(summaries);
      setStrategyEquities(equities);
    } catch (e) {
      console.error('Failed to load preset keys', e);
    }
  }, []);

  useEffect(() => {
    loadPresetKeysAndData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const savePreset = useCallback(() => {
    if (typeof window === 'undefined') return;
    const name = presetName.trim() || 'default';
    try {
      const key = `${PRESET_PREFIX}${name}`;
      window.localStorage.setItem(key, JSON.stringify(params));
      setInfoMessage(`已保存当前配置为策略「${name}」。`);
      loadPresetKeysAndData();
    } catch (e) {
      console.error('Failed to save preset', e);
      setInfoMessage('保存配置失败，请检查浏览器存储设置。');
    }
  }, [params, presetName, loadPresetKeysAndData]);

  const loadPreset = useCallback((name?: string) => {
    if (typeof window === 'undefined') return;
    try {
      const targetName = (name ?? presetName).trim() || 'default';
      const key = `${PRESET_PREFIX}${targetName}`;
      const raw = window.localStorage.getItem(key);
      if (!raw) {
        console.log('No preset found for', key);
        setInfoMessage('当前没有已保存的本地配置，可先调整参数后点击保存。');
        return;
      }
      const parsed = JSON.parse(raw);
      setParams(prev => ({
        ...prev,
        ...parsed,
      }));
      setInfoMessage(`已从本地加载策略「${targetName}」。`);
    } catch (e) {
      console.error('Failed to load preset', e);
      setInfoMessage('加载配置失败，已忽略本地数据。');
    }
  }, []);

  const deletePreset = useCallback((name: string) => {
    if (typeof window === 'undefined') return;
    const targetName = name.trim();
    if (!targetName) return;
    try {
      const key = `${PRESET_PREFIX}${targetName}`;
      window.localStorage.removeItem(key);
      window.localStorage.removeItem(`${SUMMARY_PREFIX}${targetName}`);
      window.localStorage.removeItem(`${EQUITY_PREFIX}${targetName}`);
      setInfoMessage(`已删除本地策略「${targetName}」。`);
      loadPresetKeysAndData();
    } catch (e) {
      console.error('Failed to delete preset', e);
      setInfoMessage('删除本地策略失败。');
    }
  }, [loadPresetKeysAndData]);

  useEffect(() => {
    setInfoMessage(null);
  }, [params.symbol, params.lookback_days, params.attention_quantile, params.max_daily_return, params.holding_days, params.stop_loss_pct, params.take_profit_pct, params.max_holding_days, params.position_size]);

  async function run() {
    setLoading(true); setError(null);
    try {
      const res = await runBasicAttentionBacktest(params);
      setResult(res);
      setMultiResult(null);

      if (typeof window !== 'undefined') {
        const name = presetName.trim() || 'default';
        const summaryKey = `${SUMMARY_PREFIX}${name}`;
        const equityKey = `${EQUITY_PREFIX}${name}`;
        try {
          window.localStorage.setItem(summaryKey, JSON.stringify(res.summary));
          window.localStorage.setItem(equityKey, JSON.stringify(res.equity_curve));
          setStrategySummaries(prev => ({ ...prev, [name]: res.summary }));
          setStrategyEquities(prev => ({ ...prev, [name]: res.equity_curve }));
        } catch (e) {
          console.error('Failed to persist backtest summary/equity for preset', name, e);
        }
      }
    } catch (e: any) {
      setError(e?.message || 'Backtest failed');
    } finally {
      setLoading(false);
    }
  }

  async function runMulti() {
    setLoading(true); setError(null);
    try {
      const baseSymbol = params.symbol || 'ZECUSDT';
      const base = baseSymbol.replace('USDT', '');
      const symbols = [baseSymbol, 'BTCUSDT', 'ETHUSDT'].filter((v, idx, arr) => arr.indexOf(v) === idx);
      const res = await runMultiSymbolBacktest({
        symbols,
        lookback_days: params.lookback_days,
        attention_quantile: params.attention_quantile,
        max_daily_return: params.max_daily_return,
        holding_days: params.holding_days,
        stop_loss_pct: params.stop_loss_pct,
        take_profit_pct: params.take_profit_pct,
        max_holding_days: params.max_holding_days,
        position_size: params.position_size,
      });
      setMultiResult(res);
      const symbolsFromResult = Object.keys(res.per_symbol_equity_curves || {});
      setSelectedMultiSymbol(symbolsFromResult[0] ?? null);
      setResult(null);
    } catch (e: any) {
      setError(e?.message || 'Multi backtest failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <h3 className="text-lg font-semibold">Basic Attention Strategy</h3>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          当前策略要点：
          止损 {params.stop_loss_pct != null ? `${(params.stop_loss_pct * 100).toFixed(1)}%` : '未设置'}，
          止盈 {params.take_profit_pct != null ? `${(params.take_profit_pct * 100).toFixed(1)}%` : '未设置'}，
          最长持仓 {params.max_holding_days ?? params.holding_days} 天，
          仓位 {(params.position_size * 100).toFixed(0)}%
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="h-7 rounded border bg-background px-2 text-xs"
            placeholder="策略名称，如 trend-1"
            value={presetName}
            onChange={e => setPresetName(e.target.value)}
          />
          <Button variant="outline" size="sm" onClick={savePreset}>保存为新策略</Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadPreset()}
            disabled={!availablePresets.length}
          >
            加载当前名称策略
          </Button>
        </div>
      </div>

      {availablePresets.length > 0 && (
        <div className="space-y-2 text-xs text-muted-foreground">
          <div className="flex flex-wrap items-center gap-2">
            <span>已保存策略：</span>
            <div className="flex flex-wrap gap-1">
              {availablePresets.map(name => (
                <div
                  key={name}
                  className="flex items-center gap-1 rounded border bg-background px-2 py-0.5"
                >
                  <button
                    type="button"
                    className="underline-offset-2 hover:underline"
                    onClick={() => {
                      setPresetName(name);
                      loadPreset(name);
                    }}
                  >
                    {name}
                  </button>
                  <button
                    type="button"
                    aria-label={`删除策略 ${name}`}
                    className="text-xs text-muted-foreground hover:text-red-500"
                    onClick={() => deletePreset(name)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          <StrategyOverview
            availablePresets={availablePresets}
            summaries={strategySummaries}
            equities={strategyEquities}
            selectedComparePresets={selectedComparePresets}
            onToggleCompare={name => {
              setSelectedComparePresets(prev => {
                const exists = prev.includes(name);
                if (exists) return prev.filter(n => n !== name);
                if (prev.length >= 3) return prev;
                return [...prev, name];
              });
            }}
            onLoadPreset={name => {
              setPresetName(name);
              loadPreset(name);
            }}
          />
        </div>
      )}

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
        <label className="flex flex-col gap-1 group cursor-help">
          <span
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit"
            title="止损（%）：达到该跌幅时强制平仓。"
          >
            止损 (%)
          </span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            step="0.5"
            value={params.stop_loss_pct != null ? params.stop_loss_pct * 100 : ''}
            onChange={e => {
              const v = e.target.value;
              setParams(p => ({
                ...p,
                stop_loss_pct: v === '' ? null : Number(v) / 100,
              }));
            }}
          />
        </label>
        <label className="flex flex-col gap-1 group cursor-help">
          <span
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit"
            title="止盈（%）：达到该涨幅时强制平仓。"
          >
            止盈 (%)
          </span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            step="0.5"
            value={params.take_profit_pct != null ? params.take_profit_pct * 100 : ''}
            onChange={e => {
              const v = e.target.value;
              setParams(p => ({
                ...p,
                take_profit_pct: v === '' ? null : Number(v) / 100,
              }));
            }}
          />
        </label>
        <label className="flex flex-col gap-1 group cursor-help">
          <span
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit"
            title="最长持仓天数：超过这个天数强制平仓（即便没有触发止损/止盈）。"
          >
            最长持仓天数
          </span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            value={params.max_holding_days ?? ''}
            onChange={e => {
              const v = e.target.value;
              setParams(p => ({
                ...p,
                max_holding_days: v === '' ? null : Number(v),
              }));
            }}
          />
        </label>
        <label className="flex flex-col gap-1 group cursor-help">
          <span
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit"
            title="仓位大小：每笔交易使用资金比例（用于影响 equity curve）。"
          >
            仓位大小
          </span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            min={0}
            max={1}
            step="0.1"
            value={params.position_size}
            onChange={e => setParams(p => ({...p, position_size: Number(e.target.value)}))}
          />
        </label>
        <div className="flex items-end gap-2">
          <Button onClick={run} disabled={loading}>{loading ? 'Running...' : 'Single Backtest'}</Button>
          <Button variant="outline" onClick={runMulti} disabled={loading}>{loading ? 'Running...' : 'Multi-Asset'}</Button>
        </div>
      </div>

      {error && <div className="text-red-500 text-sm">{error}</div>}
      {infoMessage && !error && (
        <div className="text-xs text-muted-foreground">{infoMessage}</div>
      )}

      {availablePresets.length > 0 && selectedComparePresets.length > 0 && (
        <MultiStrategyComparison
          selectedPresets={selectedComparePresets}
          equities={strategyEquities}
        />
      )}

      {result && (
        <div className="space-y-4">
          {result.trades.length === 0 && (
            <div className="rounded-md border border-dashed border-muted-foreground/40 bg-muted/40 p-3 text-xs text-muted-foreground">
              在当前参数下没有产生交易，可以尝试降低 attention_quantile 或放宽 max_daily_return。
            </div>
          )}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
            <Stat label="Trades" value={result.summary.total_trades} />
            <Stat label="Win Rate" value={`${result.summary.win_rate.toFixed(1)}%`} />
            <Stat label="Avg Return" value={`${(result.summary.avg_return*100).toFixed(2)}%`} />
            <Stat label="Cumulative" value={`${(result.summary.cumulative_return*100).toFixed(2)}%`} />
            <Stat label="Max DD" value={`${(result.summary.max_drawdown*100).toFixed(2)}%`} />
          </div>

          {result.equity_curve && result.equity_curve.length > 0 && (
            <EquityCurve
              title="Equity Curve"
              points={result.equity_curve}
            />
          )}

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

      {multiResult && (
        <div className="space-y-4">
          <h4 className="text-md font-semibold">Multi-Asset Comparison</h4>
          {Object.values(multiResult.per_symbol_summary).every(s => 'error' in s || s.total_trades === 0) && (
            <div className="rounded-md border border-dashed border-muted-foreground/40 bg-muted/40 p-3 text-xs text-muted-foreground">
              在当前参数下多币种回测没有产生交易，可以尝试降低 attention_quantile 或放宽 max_daily_return。
            </div>
          )}
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="text-left py-2">Symbol</th>
                  <th className="text-right py-2">Trades</th>
                  <th className="text-right py-2">Win Rate</th>
                  <th className="text-right py-2">Cumulative</th>
                  <th className="text-right py-2">Max DD</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(multiResult.per_symbol_summary).map(([sym, summary]) => (
                  <tr key={sym} className="border-t border-border/50">
                    <td className="py-1 font-medium">{sym}</td>
                    {'error' in summary ? (
                      <td className="py-1 text-red-500 text-xs" colSpan={4}>{summary.error}</td>
                    ) : (
                      <>
                        <td className="text-right py-1">{summary.total_trades}</td>
                        <td className="text-right py-1">{summary.win_rate.toFixed(1)}%</td>
                        <td className="text-right py-1">{(summary.cumulative_return * 100).toFixed(2)}%</td>
                        <td className="text-right py-1">{(summary.max_drawdown * 100).toFixed(2)}%</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {multiResult.per_symbol_equity_curves && Object.keys(multiResult.per_symbol_equity_curves).length > 0 && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>查看单一标的权益曲线：</span>
                <div className="flex flex-wrap gap-2">
                  {Object.keys(multiResult.per_symbol_equity_curves).map(sym => (
                    <button
                      key={sym}
                      type="button"
                      onClick={() => setSelectedMultiSymbol(sym)}
                      className={`rounded border px-2 py-0.5 text-xs ${selectedMultiSymbol === sym ? 'bg-primary text-primary-foreground' : 'bg-background hover:bg-muted'}`}
                    >
                      {sym}
                    </button>
                  ))}
                </div>
              </div>
              {selectedMultiSymbol &&
                multiResult.per_symbol_equity_curves[selectedMultiSymbol] &&
                multiResult.per_symbol_equity_curves[selectedMultiSymbol].length > 0 && (
                  <EquityCurve
                    title={`Equity Curve - ${selectedMultiSymbol}`}
                    points={multiResult.per_symbol_equity_curves[selectedMultiSymbol]}
                  />
                )}
            </div>
          )}
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

function StrategyOverview({
  availablePresets,
  summaries,
  equities,
  selectedComparePresets,
  onToggleCompare,
  onLoadPreset,
}: {
  availablePresets: string[];
  summaries: Record<string, BacktestSummary>;
  equities: Record<string, EquityPoint[]>;
  selectedComparePresets: string[];
  onToggleCompare: (name: string) => void;
  onLoadPreset: (name: string) => void;
}) {
  const rows = useMemo(() => {
    return availablePresets
      .map(name => ({ name, summary: summaries[name] }))
      .filter(row => !!row.summary)
      .sort((a, b) => (b.summary!.cumulative_return - a.summary!.cumulative_return));
  }, [availablePresets, summaries]);

  if (!rows.length) return null;

  return (
    <div className="w-full rounded border bg-background p-3">
      <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>策略概览（按累计收益从高到低排序）</span>
        <span>勾选最多 3 个策略用于权益曲线对比</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 text-left">对比</th>
              <th className="py-1 text-left">策略名</th>
              <th className="py-1 text-right">交易数</th>
              <th className="py-1 text-right">胜率</th>
              <th className="py-1 text-right">累计收益</th>
              <th className="py-1 text-right">最大回撤</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ name, summary }) => (
              <tr key={name} className="border-t border-border/50">
                <td className="py-1 text-center">
                  <input
                    type="checkbox"
                    className="h-3 w-3 cursor-pointer"
                    checked={selectedComparePresets.includes(name)}
                    onChange={() => onToggleCompare(name)}
                  />
                </td>
                <td className="py-1">
                  <button
                    type="button"
                    className="text-left text-xs underline-offset-2 hover:underline"
                    onClick={() => onLoadPreset(name)}
                  >
                    {name}
                  </button>
                  {!equities[name] && (
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      （需先运行回测）
                    </span>
                  )}
                </td>
                <td className="py-1 text-right">{summary!.total_trades}</td>
                <td className="py-1 text-right">{summary!.win_rate.toFixed(1)}%</td>
                <td className="py-1 text-right">{(summary!.cumulative_return * 100).toFixed(2)}%</td>
                <td className="py-1 text-right">{(summary!.max_drawdown * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MultiStrategyComparison({
  selectedPresets,
  equities,
}: {
  selectedPresets: string[];
  equities: Record<string, EquityPoint[]>;
}) {
  const width = 100;
  const height = 40;

  const series = useMemo(() => {
    const result: { name: string; points: EquityPoint[] }[] = [];
    selectedPresets.forEach(name => {
      const pts = equities[name];
      if (pts && pts.length > 0) {
        result.push({ name, points: pts });
      }
    });
    return result;
  }, [selectedPresets, equities]);

  const { paths, minEquity, maxEquity } = useMemo(() => {
    if (!series.length) {
      return { paths: [], minEquity: 0, maxEquity: 0 };
    }
    const allValues = series.flatMap(s => s.points.map(p => p.equity));
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const span = max - min || 1;

    const colors = ['stroke-primary', 'stroke-emerald-400', 'stroke-amber-400'];

    const built = series.map((s, idx) => {
      const pts = s.points;
      const stepX = pts.length > 1 ? width / (pts.length - 1) : 0;
      const d = pts
        .map((p, i) => {
          const x = i * stepX;
          const y = height - ((p.equity - min) / span) * height;
          return `${i === 0 ? 'M' : 'L'}${x},${y}`;
        })
        .join(' ');
      return { name: s.name, d, colorClass: colors[idx % colors.length] };
    });

    return { paths: built, minEquity: min, maxEquity: max };
  }, [series, width, height]);

  if (!series.length) {
    return (
      <div className="rounded border border-dashed bg-muted/40 p-3 text-xs text-muted-foreground">
        选择的策略暂无本地权益曲线数据，请先加载并运行对应策略的回测。
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded border bg-background p-3">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>多策略权益曲线对比</span>
        <span>{`区间权益：${minEquity.toFixed(2)} → ${maxEquity.toFixed(2)}`}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-28 w-full">
        {paths.map(p => (
          <path
            key={p.name}
            d={p.d}
            fill="none"
            strokeWidth={1.5}
            className={p.colorClass}
          />
        ))}
      </svg>
      <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
        {paths.map(p => (
          <div key={p.name} className="flex items-center gap-1">
            <span className={`h-2 w-4 rounded ${p.colorClass.replace('stroke', 'bg')}`} />
            <span>{p.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function EquityCurve({ title, points }: { title: string; points: { datetime: string; equity: number }[] }) {
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
        <span>
          {`区间权益：${minEquity.toFixed(2)} → ${maxEquity.toFixed(2)}`}
        </span>
      </div>
      <svg viewBox="0 0 100 40" className="h-24 w-full">
        <path d={path} fill="none" strokeWidth={1.5} className="stroke-primary" />
      </svg>
    </div>
  );
}
