"use client";

/**
 * 历史回测 Tab
 * 
 * 包含：
 * 1. Basic Attention Strategy 回测
 * 2. 注意力轮动策略回测
 * 3. 事件表现分析
 */

import React, { useState, useCallback, useMemo } from 'react';
import { TrendingUp, RefreshCw, BarChart3, Layers, Zap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAsyncCallback, useAsync } from '@/lib/hooks';
import { backtestService, attentionService } from '@/lib/services';
import { BacktestPanel } from '@/components/backtest';
import { EquityCurve, StatCard } from '@/components/backtest';
import type { AttentionRotationResult, EventPerformanceTable, EventPerformanceRow } from '@/types/models/backtest';

// ==================== 注意力轮动策略面板 ====================

function AttentionRotationPanel() {
  const [symbols, setSymbols] = useState<string[]>(['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ZECUSDT']);
  const [rebalanceDays, setRebalanceDays] = useState(7);
  const [lookbackDays, setLookbackDays] = useState(30);
  const [topK, setTopK] = useState(2);
  const [attentionSource, setAttentionSource] = useState<'composite' | 'news_channel'>('composite');
  const [newSymbol, setNewSymbol] = useState('');

  const {
    execute: runRotation,
    data: result,
    loading,
    error,
  } = useAsyncCallback(async () => {
    return await backtestService.runAttentionRotationBacktest({
      symbols,
      attentionSource,
      rebalanceDays,
      lookbackDays,
      topK,
    });
  });

  const addSymbol = useCallback(() => {
    const sym = newSymbol.trim().toUpperCase();
    if (sym && !symbols.includes(sym)) {
      setSymbols(prev => [...prev, sym.endsWith('USDT') ? sym : `${sym}USDT`]);
      setNewSymbol('');
    }
  }, [newSymbol, symbols]);

  const removeSymbol = useCallback((sym: string) => {
    setSymbols(prev => prev.filter(s => s !== sym));
  }, []);

  return (
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Layers className="w-5 h-5 text-primary" />
          Attention Rotation Strategy
        </h3>
        <span className="text-xs text-muted-foreground">
          基于注意力分数的动态轮动策略
        </span>
      </div>

      {/* 币种池 */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">币种池：</span>
          {symbols.map(sym => (
            <span
              key={sym}
              className="inline-flex items-center gap-1 rounded border bg-background px-2 py-0.5"
            >
              {sym.replace('USDT', '')}
              <button
                type="button"
                className="text-muted-foreground hover:text-red-500"
                onClick={() => removeSymbol(sym)}
              >
                ×
              </button>
            </span>
          ))}
          <div className="flex items-center gap-1">
            <input
              className="h-7 w-20 rounded border bg-background px-2 text-xs"
              placeholder="添加币种"
              value={newSymbol}
              onChange={e => setNewSymbol(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addSymbol()}
            />
            <Button variant="outline" size="sm" onClick={addSymbol}>
              +
            </Button>
          </div>
        </div>
      </div>

      {/* 参数配置 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">再平衡周期（天）</span>
          <input
            type="number"
            min={1}
            className="px-2 py-1 bg-background border rounded"
            value={rebalanceDays}
            onChange={e => setRebalanceDays(Number(e.target.value))}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">注意力回看（天）</span>
          <input
            type="number"
            min={1}
            className="px-2 py-1 bg-background border rounded"
            value={lookbackDays}
            onChange={e => setLookbackDays(Number(e.target.value))}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">持仓数量（Top K）</span>
          <input
            type="number"
            min={1}
            max={symbols.length}
            className="px-2 py-1 bg-background border rounded"
            value={topK}
            onChange={e => setTopK(Number(e.target.value))}
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">注意力来源</span>
          <select
            className="px-2 py-1 bg-background border rounded text-sm"
            value={attentionSource}
            onChange={e => setAttentionSource(e.target.value as any)}
          >
            <option value="composite">Composite</option>
            <option value="news_channel">News Channel</option>
          </select>
        </label>

        <div className="flex items-end">
          <Button onClick={() => runRotation()} disabled={loading || symbols.length < 2}>
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <TrendingUp className="w-4 h-4 mr-1" />
                Run Rotation
              </>
            )}
          </Button>
        </div>
      </div>

      {error && <div className="text-red-500 text-sm">{error.message}</div>}

      {/* 结果展示 */}
      {result && (
        <div className="space-y-4 relative">
          {/* 运行中提示 - 保持旧结果可见 */}
          {loading && (
            <div className="absolute top-2 right-2 z-10 flex items-center gap-2 bg-background/90 backdrop-blur px-3 py-1.5 rounded-md border text-xs text-muted-foreground">
              <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              正在重新计算...
            </div>
          )}
          {/* 统计摘要 */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <StatCard
              label="Total Return"
              value={`${(result.summary.totalReturn * 100).toFixed(2)}%`}
              variant={result.summary.totalReturn >= 0 ? 'positive' : 'negative'}
            />
            <StatCard
              label="Annualized"
              value={`${(result.summary.annualizedReturn * 100).toFixed(2)}%`}
              variant={result.summary.annualizedReturn >= 0 ? 'positive' : 'negative'}
            />
            <StatCard
              label="Max Drawdown"
              value={`${(result.summary.maxDrawdown * 100).toFixed(2)}%`}
              variant="negative"
            />
            <StatCard
              label="Volatility"
              value={`${(result.summary.volatility * 100).toFixed(2)}%`}
            />
            <StatCard
              label="Sharpe Ratio"
              value={result.summary.sharpe.toFixed(2)}
              variant={result.summary.sharpe >= 1 ? 'positive' : undefined}
            />
            <StatCard
              label="Rebalances"
              value={result.summary.numRebalances}
            />
          </div>

          {/* 权益曲线 */}
          {result.equityCurve.length > 0 && (
            <EquityCurve
              title="Rotation Strategy Equity Curve"
              points={result.equityCurve}
            />
          )}

          {/* 再平衡日志 */}
          {result.rebalanceLog.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Rebalance Log</h4>
              <div className="max-h-60 overflow-auto">
                <table className="w-full text-xs">
                  <thead className="text-muted-foreground sticky top-0 bg-card">
                    <tr>
                      <th className="text-left py-1">Date</th>
                      <th className="text-left py-1">Selected Symbols</th>
                      <th className="text-left py-1">Attention Values</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rebalanceLog.map((log, i) => (
                      <tr key={i} className="border-t border-border/50">
                        <td className="py-1">{new Date(log.rebalanceDate).toLocaleDateString()}</td>
                        <td className="py-1">{log.selectedSymbols.join(', ')}</td>
                        <td className="py-1 font-mono text-muted-foreground">
                          {Object.entries(log.attentionValues)
                            .sort(([, a], [, b]) => b - a)
                            .slice(0, 5)
                            .map(([sym, val]) => `${sym.replace('USDT', '')}:${val.toFixed(2)}`)
                            .join(' | ')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==================== 事件表现分析面板 ====================

function EventPerformancePanel() {
  const [symbol, setSymbol] = useState('ZECUSDT');

  const {
    execute: fetchPerformance,
    data: performanceData,
    loading,
    error,
  } = useAsyncCallback(async (sym: string) => {
    return await backtestService.getEventPerformance(sym);
  });

  const handleSearch = useCallback(() => {
    const sym = symbol.trim().toUpperCase();
    fetchPerformance(sym.endsWith('USDT') ? sym : `${sym}USDT`);
  }, [symbol, fetchPerformance]);

  return (
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Zap className="w-5 h-5 text-amber-500" />
          Event Performance Analysis
        </h3>
        <span className="text-xs text-muted-foreground">
          分析不同事件类型后的价格表现
        </span>
      </div>

      {/* 查询表单 */}
      <div className="flex items-center gap-3">
        <input
          className="h-9 w-40 rounded border bg-background px-3 text-sm"
          placeholder="输入币种，如 ZEC"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
        <Button onClick={handleSearch} disabled={loading}>
          {loading ? (
            <>
              <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
              Loading...
            </>
          ) : (
            <>
              <BarChart3 className="w-4 h-4 mr-1" />
              Analyze
            </>
          )}
        </Button>
      </div>

      {error && <div className="text-red-500 text-sm">{error.message}</div>}

      {/* 结果表格 */}
      {performanceData && performanceData.rows.length > 0 && (
        <div className="space-y-2 relative">
          {/* 运行中提示 - 保持旧结果可见 */}
          {loading && (
            <div className="absolute top-2 right-2 z-10 flex items-center gap-2 bg-background/90 backdrop-blur px-3 py-1.5 rounded-md border text-xs text-muted-foreground">
              <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              正在更新...
            </div>
          )}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Symbol: {performanceData.symbol}</span>
            <span>Updated: {new Date(performanceData.updatedAt).toLocaleString()}</span>
          </div>
          
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="text-left py-2">Event Type</th>
                  <th className="text-right py-2">Count</th>
                  <th className="text-right py-2">1D Ret</th>
                  <th className="text-right py-2">3D Ret</th>
                  <th className="text-right py-2">5D Ret</th>
                  <th className="text-right py-2">10D Ret</th>
                  <th className="text-right py-2">1D Win%</th>
                  <th className="text-right py-2">5D Win%</th>
                </tr>
              </thead>
              <tbody>
                {performanceData.rows.map((row, i) => (
                  <tr key={i} className="border-t border-border/50">
                    <td className="py-1 font-medium">{row.eventType}</td>
                    <td className="text-right py-1">{row.count}</td>
                    <td className={`text-right py-1 ${row.avgReturn1d >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {(row.avgReturn1d * 100).toFixed(2)}%
                    </td>
                    <td className={`text-right py-1 ${row.avgReturn3d >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {(row.avgReturn3d * 100).toFixed(2)}%
                    </td>
                    <td className={`text-right py-1 ${row.avgReturn5d >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {(row.avgReturn5d * 100).toFixed(2)}%
                    </td>
                    <td className={`text-right py-1 ${row.avgReturn10d >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {(row.avgReturn10d * 100).toFixed(2)}%
                    </td>
                    <td className={`text-right py-1 ${row.winRate1d >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {row.winRate1d.toFixed(1)}%
                    </td>
                    <td className={`text-right py-1 ${row.winRate5d >= 50 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                      {row.winRate5d.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {performanceData && performanceData.rows.length === 0 && (
        <div className="rounded-md border border-dashed border-muted-foreground/40 bg-muted/40 p-4 text-center text-sm text-muted-foreground">
          暂无该币种的事件表现数据
        </div>
      )}
    </div>
  );
}

// ==================== 主 Tab 组件 ====================

export default function BacktestTab() {
  return (
    <div className="space-y-6 p-4">
      {/* 标题和说明 */}
      <div className="space-y-1">
        <h2 className="text-2xl font-bold">历史回测</h2>
        <p className="text-muted-foreground">
          基于历史数据验证注意力驱动的交易策略表现
        </p>
      </div>

      {/* 基础注意力策略 */}
      <BacktestPanel />

      {/* 注意力轮动策略 */}
      <AttentionRotationPanel />

      {/* 事件表现分析 */}
      <EventPerformancePanel />
    </div>
  );
}
