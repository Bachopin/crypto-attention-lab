"use client";

/**
 * BacktestPanel - 重构版本
 * 
 * 使用服务层 + hooks 模式，拆分子组件
 */

import React, { useState, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { useSettings } from '@/components/SettingsProvider';
import { useAsyncCallback } from '@/lib/hooks';
import { backtestService } from '@/lib/services';
import type { BacktestResult, MultiBacktestResult, EquityPoint, BacktestSummary } from '@/types/models/backtest';
import type { AttentionCondition } from '@/types/models/attention';

import { StatGrid } from './StatCard';
import { EquityCurve, MultiEquityCurve } from './EquityCurve';
import { TradeTable } from './TradeTable';
import { StrategyOverview } from './StrategyOverview';
import { BacktestParamsForm } from './BacktestParamsForm';
import { useStrategyPresets } from './useStrategyPresets';
import type { 
  BacktestPanelParams, 
  AttentionConditionState,
} from './types';

interface BacktestPanelProps {
  symbol?: string;
  className?: string;
}

export function BacktestPanel({ symbol: initialSymbol, className = '' }: BacktestPanelProps) {
  const { settings } = useSettings();
  
  // 参数状态
  const [params, setParams] = useState<BacktestPanelParams>(() => ({
    symbol: initialSymbol || 'ZECUSDT',
    lookbackDays: settings.defaultWindowDays || 30,
    attentionQuantile: 0.8,
    maxDailyReturn: 0.05,
    holdingDays: 3,
    stopLossPct: 0.05,
    takeProfitPct: 0.1,
    maxHoldingDays: 5,
    positionSize: 1.0,
    attentionSource: 'legacy',
  }));

  const [attentionCondition, setAttentionCondition] = useState<AttentionConditionState>({
    enabled: false,
    source: 'composite',
    regime: 'high',
    lowerQuantile: 0.8,
    upperQuantile: 1,
    lookbackDays: settings.defaultWindowDays || 30,
  });

  // 预设管理
  const { 
    presetNames, 
    summaries, 
    equities, 
    savePreset, 
    loadPreset, 
    deletePreset,
    saveBacktestResult,
  } = useStrategyPresets();

  // UI 状态
  const [presetName, setPresetName] = useState('default');
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [selectedComparePresets, setSelectedComparePresets] = useState<string[]>([]);
  const [selectedMultiSymbol, setSelectedMultiSymbol] = useState<string | null>(null);

  // 构建 API 格式的 AttentionCondition（移到 useAsyncCallback 之前）
  const buildAttentionCondition = useCallback((): AttentionCondition | null => {
    if (!attentionCondition.enabled) return null;
    return {
      source: attentionCondition.source,
      regime: attentionCondition.regime,
      lowerQuantile: attentionCondition.regime === 'custom' ? attentionCondition.lowerQuantile : undefined,
      upperQuantile: attentionCondition.regime === 'custom' ? attentionCondition.upperQuantile : undefined,
      lookbackDays: attentionCondition.lookbackDays,
    };
  }, [attentionCondition]);

  // 单币种回测
  const { 
    execute: runBacktest, 
    data: backtestResult, 
    loading: singleLoading, 
    error: singleError,
    reset: resetSingle,
  } = useAsyncCallback(async () => {
    const condition = buildAttentionCondition();
    const result = await backtestService.runBacktest({
      symbol: params.symbol,
      lookbackDays: params.lookbackDays,
      attentionQuantile: params.attentionQuantile,
      maxDailyReturn: params.maxDailyReturn,
      holdingDays: params.holdingDays,
      stopLossPct: params.stopLossPct,
      takeProfitPct: params.takeProfitPct,
      maxHoldingDays: params.maxHoldingDays,
      positionSize: params.positionSize,
      attentionSource: params.attentionSource,
      attentionCondition: condition,
    });
    
    // 保存结果
    const name = presetName.trim() || 'default';
    saveBacktestResult(name, result.summary, result.equityCurve);
    
    return result;
  });

  // 多币种回测
  const { 
    execute: runMultiBacktest, 
    data: multiResult, 
    loading: multiLoading, 
    error: multiError,
    reset: resetMulti,
  } = useAsyncCallback(async () => {
    const base = params.symbol.replace('USDT', '');
    const symbols = [params.symbol, 'BTCUSDT', 'ETHUSDT'].filter(
      (v, idx, arr) => arr.indexOf(v) === idx
    );
    
    const condition = buildAttentionCondition();
    const result = await backtestService.runMultiBacktest(symbols, {
      lookbackDays: params.lookbackDays,
      attentionQuantile: params.attentionQuantile,
      maxDailyReturn: params.maxDailyReturn,
      holdingDays: params.holdingDays,
      stopLossPct: params.stopLossPct,
      takeProfitPct: params.takeProfitPct,
      maxHoldingDays: params.maxHoldingDays,
      positionSize: params.positionSize,
      attentionSource: params.attentionSource,
      attentionCondition: condition,
    });
    
    // 设置默认选中的 symbol
    const symbolsFromResult = Object.keys(result.perSymbolEquityCurves || {});
    setSelectedMultiSymbol(symbolsFromResult[0] ?? null);
    
    return result;
  });

  const loading = singleLoading || multiLoading;
  const error = singleError || multiError;

  // 运行单币种回测
  const handleRunSingle = useCallback(async () => {
    resetMulti();
    await runBacktest();
  }, [runBacktest, resetMulti]);

  // 运行多币种回测
  const handleRunMulti = useCallback(async () => {
    resetSingle();
    await runMultiBacktest();
  }, [runMultiBacktest, resetSingle]);

  // 保存预设
  const handleSavePreset = useCallback(() => {
    const name = presetName.trim() || 'default';
    const condition = buildAttentionCondition();
    savePreset(name, params, condition);
    setInfoMessage(`已保存当前配置为策略「${name}」。`);
  }, [presetName, params, buildAttentionCondition, savePreset]);

  // 加载预设
  const handleLoadPreset = useCallback((name: string) => {
    const loaded = loadPreset(name);
    if (loaded) {
      setParams(loaded);
      setPresetName(name);
      setInfoMessage(`已从本地加载策略「${name}」。`);
    } else {
      setInfoMessage('当前没有已保存的本地配置。');
    }
  }, [loadPreset]);

  // 删除预设
  const handleDeletePreset = useCallback((name: string) => {
    deletePreset(name);
    setInfoMessage(`已删除本地策略「${name}」。`);
  }, [deletePreset]);

  // 切换对比策略
  const handleToggleCompare = useCallback((name: string) => {
    setSelectedComparePresets(prev => {
      if (prev.includes(name)) return prev.filter(n => n !== name);
      if (prev.length >= 3) return prev;
      return [...prev, name];
    });
  }, []);

  // 构建统计数据
  const stats = useMemo(() => {
    const summary = backtestResult?.summary;
    if (!summary) return null;
    
    return [
      { 
        label: 'Trades', 
        value: summary.totalTrades, 
        tooltip: '总交易次数' 
      },
      { 
        label: 'Win Rate', 
        value: `${summary.winRate.toFixed(1)}%`, 
        tooltip: '盈利交易占比',
        variant: summary.winRate >= 50 ? 'positive' as const : 'negative' as const,
      },
      { 
        label: 'Avg Return', 
        value: `${(summary.avgReturn * 100).toFixed(2)}%`, 
        tooltip: '每笔交易平均收益率',
        variant: summary.avgReturn >= 0 ? 'positive' as const : 'negative' as const,
      },
      { 
        label: 'Cumulative', 
        value: `${(summary.cumulativeReturn * 100).toFixed(2)}%`, 
        tooltip: '累计收益率',
        variant: summary.cumulativeReturn >= 0 ? 'positive' as const : 'negative' as const,
      },
      { 
        label: 'Max DD', 
        value: `${(summary.maxDrawdown * 100).toFixed(2)}%`, 
        tooltip: '最大回撤',
        variant: 'negative' as const,
      },
    ];
  }, [backtestResult]);

  // 策略摘要文本
  const strategySummaryText = useMemo(() => {
    return `止损 ${params.stopLossPct != null ? `${(params.stopLossPct * 100).toFixed(1)}%` : '未设置'}，
止盈 ${params.takeProfitPct != null ? `${(params.takeProfitPct * 100).toFixed(1)}%` : '未设置'}，
最长持仓 ${params.maxHoldingDays ?? params.holdingDays} 天，
仓位 ${(params.positionSize * 100).toFixed(0)}%，
信号源 ${params.attentionSource === 'legacy' ? 'Legacy Attention' : 'Composite Attention'}`;
  }, [params]);

  // 多策略对比曲线数据
  const compareSeries = useMemo(() => {
    return selectedComparePresets
      .filter(name => equities[name]?.length > 0)
      .map(name => ({ name, points: equities[name] }));
  }, [selectedComparePresets, equities]);

  return (
    <div className={`bg-card rounded-lg border p-4 space-y-4 ${className}`}>
      <h3 className="text-lg font-semibold">Basic Attention Strategy</h3>
      
      {/* 策略摘要和预设管理 */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>当前策略要点：{strategySummaryText}</span>
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="h-7 rounded border bg-background px-2 text-xs"
            placeholder="策略名称，如 trend-1"
            value={presetName}
            onChange={e => setPresetName(e.target.value)}
          />
          <Button variant="outline" size="sm" onClick={handleSavePreset}>
            保存为新策略
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleLoadPreset(presetName)}
            disabled={!presetNames.length}
          >
            加载当前名称策略
          </Button>
        </div>
      </div>

      {/* 已保存策略列表 */}
      {presetNames.length > 0 && (
        <div className="space-y-2 text-xs text-muted-foreground">
          <div className="flex flex-wrap items-center gap-2">
            <span>已保存策略：</span>
            <div className="flex flex-wrap gap-1">
              {presetNames.map(name => (
                <div
                  key={name}
                  className="flex items-center gap-1 rounded border bg-background px-2 py-0.5"
                >
                  <button
                    type="button"
                    className="underline-offset-2 hover:underline"
                    onClick={() => handleLoadPreset(name)}
                  >
                    {name}
                  </button>
                  <button
                    type="button"
                    aria-label={`删除策略 ${name}`}
                    className="text-xs text-muted-foreground hover:text-red-500"
                    onClick={() => handleDeletePreset(name)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          <StrategyOverview
            presetNames={presetNames}
            summaries={summaries}
            equities={equities}
            selectedComparePresets={selectedComparePresets}
            onToggleCompare={handleToggleCompare}
            onLoadPreset={handleLoadPreset}
          />
        </div>
      )}

      {/* 参数表单 */}
      <BacktestParamsForm
        params={params}
        onParamsChange={setParams}
        attentionCondition={attentionCondition}
        onAttentionConditionChange={setAttentionCondition}
        onRunSingle={handleRunSingle}
        onRunMulti={handleRunMulti}
        loading={loading}
      />

      {/* 注意力条件摘要 */}
      {attentionCondition.enabled && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">当前条件摘要：</span>
          <span className="font-mono bg-muted px-2 py-0.5 rounded">
            {backtestService.formatConditionSummary(buildAttentionCondition())}
          </span>
        </div>
      )}

      {/* 错误和信息提示 */}
      {error && <div className="text-red-500 text-sm">{error.message}</div>}
      {infoMessage && !error && (
        <div className="text-xs text-muted-foreground">{infoMessage}</div>
      )}

      {/* 多策略对比曲线 */}
      {compareSeries.length > 0 && (
        <MultiEquityCurve series={compareSeries} />
      )}

      {/* 单币种回测结果 */}
      {backtestResult && (
        <div className="space-y-4 relative">
          {/* 运行中提示 - 保持旧结果可见 */}
          {singleLoading && (
            <div className="absolute top-2 right-2 z-10 flex items-center gap-2 bg-background/90 backdrop-blur px-3 py-1.5 rounded-md border text-xs text-muted-foreground">
              <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              正在重新计算...
            </div>
          )}
          {backtestResult.meta?.attentionSource && (
            <div className="text-xs text-muted-foreground">
              信号源：{backtestResult.meta.attentionSource === 'composite' ? 'Composite Attention' : 'Legacy Attention'}
              {backtestResult.meta.signalField && `（字段 ${backtestResult.meta.signalField}）`}
              {backtestResult.meta.attentionCondition && (
                <span className="ml-2 font-mono bg-muted px-1 py-0.5 rounded">
                  Regime: {backtestService.formatConditionSummary(backtestResult.meta.attentionCondition)}
                </span>
              )}
            </div>
          )}

          {stats && <StatGrid stats={stats} columns={5} />}

          {backtestResult.equityCurve.length > 0 && (
            <EquityCurve
              title="Equity Curve"
              points={backtestResult.equityCurve}
            />
          )}

          <TradeTable trades={backtestResult.trades} />
        </div>
      )}

      {/* 多币种回测结果 */}
      {multiResult && (
        <div className="space-y-4 relative">
          {/* 运行中提示 - 保持旧结果可见 */}
          {multiLoading && (
            <div className="absolute top-2 right-2 z-10 flex items-center gap-2 bg-background/90 backdrop-blur px-3 py-1.5 rounded-md border text-xs text-muted-foreground">
              <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              正在重新计算...
            </div>
          )}
          <h4 className="text-md font-semibold">Multi-Asset Comparison</h4>
          
          {multiResult.meta?.attentionSource && (
            <div className="text-xs text-muted-foreground">
              多币种回测信号源：{multiResult.meta.attentionSource === 'composite' ? 'Composite Attention' : 'Legacy Attention'}
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
                {Object.entries(multiResult.perSymbolSummary).map(([sym, summary]) => (
                  <tr key={sym} className="border-t border-border/50">
                    <td className="py-1 font-medium">{sym}</td>
                    {summary.error ? (
                      <td className="py-1 text-red-500 text-xs" colSpan={4}>
                        {summary.error}
                      </td>
                    ) : (
                      <>
                        <td className="text-right py-1">{summary.totalTrades}</td>
                        <td className="text-right py-1">{summary.winRate.toFixed(1)}%</td>
                        <td className={`text-right py-1 ${summary.cumulativeReturn >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                          {(summary.cumulativeReturn * 100).toFixed(2)}%
                        </td>
                        <td className="text-right py-1 text-red-600 dark:text-red-400">
                          {(summary.maxDrawdown * 100).toFixed(2)}%
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 多币种权益曲线切换 */}
          {multiResult.perSymbolEquityCurves && Object.keys(multiResult.perSymbolEquityCurves).length > 0 && (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>查看单一标的权益曲线：</span>
                <div className="flex flex-wrap gap-2">
                  {Object.keys(multiResult.perSymbolEquityCurves).map(sym => (
                    <button
                      key={sym}
                      type="button"
                      onClick={() => setSelectedMultiSymbol(sym)}
                      className={`rounded border px-2 py-0.5 text-xs ${
                        selectedMultiSymbol === sym 
                          ? 'bg-primary text-primary-foreground' 
                          : 'bg-background hover:bg-muted'
                      }`}
                    >
                      {sym}
                    </button>
                  ))}
                </div>
              </div>
              
              {selectedMultiSymbol && multiResult.perSymbolEquityCurves[selectedMultiSymbol]?.length > 0 && (
                <EquityCurve
                  title={`Equity Curve - ${selectedMultiSymbol}`}
                  subtitle={multiResult.perSymbolMeta?.[selectedMultiSymbol]?.signal_field}
                  points={multiResult.perSymbolEquityCurves[selectedMultiSymbol]}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default BacktestPanel;
