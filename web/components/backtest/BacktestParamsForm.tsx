/**
 * 回测参数表单组件
 */

import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { fetchSymbols } from '@/lib/api';
import type { BacktestPanelParams, AttentionConditionState, AttentionSource, AttentionConditionSource, AttentionRegime } from './types';

interface BacktestParamsFormProps {
  params: BacktestPanelParams;
  onParamsChange: (params: BacktestPanelParams) => void;
  attentionCondition: AttentionConditionState;
  onAttentionConditionChange: (condition: AttentionConditionState) => void;
  onRunSingle: () => void;
  onRunMulti: () => void;
  loading: boolean;
}

export function BacktestParamsForm({
  params,
  onParamsChange,
  attentionCondition,
  onAttentionConditionChange,
  onRunSingle,
  onRunMulti,
  loading,
}: BacktestParamsFormProps) {
  const [availableSymbols, setAvailableSymbols] = useState<string[]>([]);
  const [symbolsLoading, setSymbolsLoading] = useState(false);
  const [symbolsError, setSymbolsError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setSymbolsLoading(true);
        const res = await fetchSymbols();
        if (!mounted) return;
        const syms = (res.symbols || []).map(s => s.endsWith('USDT') ? s : `${s}USDT`);
        setAvailableSymbols(syms);
        // 如果当前选择不在列表，保留现有值但不强制重置
      } catch (e: any) {
        if (!mounted) return;
        setSymbolsError(e?.message || 'Failed to load symbols');
      } finally {
        if (mounted) setSymbolsLoading(false);
      }
    })();
    return () => { mounted = false };
  }, []);
  const updateParam = <K extends keyof BacktestPanelParams>(
    key: K,
    value: BacktestPanelParams[K]
  ) => {
    onParamsChange({ ...params, [key]: value });
  };

  const updateCondition = <K extends keyof AttentionConditionState>(
    key: K,
    value: AttentionConditionState[K]
  ) => {
    onAttentionConditionChange({ ...attentionCondition, [key]: value });
  };

  return (
    <div className="space-y-4">
      {/* 代币选择 */}
      <div className="rounded border bg-background p-3 text-sm">
        <div className="flex items-center justify-between">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">选择代币</span>
            <div className="flex items-center gap-2">
              <select
                className="px-2 py-1 bg-background border rounded text-sm"
                value={params.symbol}
                onChange={e => updateParam('symbol', e.target.value as any)}
              >
                {/* 当前值优先显示，避免不在列表时丢失 */}
                {(!availableSymbols.includes(params.symbol)) && (
                  <option value={params.symbol}>{params.symbol}</option>
                )}
                {availableSymbols.map(sym => (
                  <option key={sym} value={sym}>{sym}</option>
                ))}
              </select>
              {symbolsLoading && (
                <span className="text-[10px] text-muted-foreground">加载中…</span>
              )}
            </div>
          </label>
          {symbolsError && (
            <span className="text-[10px] text-red-500">{symbolsError}</span>
          )}
        </div>
        <span className="text-xs text-muted-foreground">只显示当前已开启自动更新的代币。</span>
      </div>

      {/* 基础参数 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        <label className="flex flex-col gap-1 cursor-help">
          <span 
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" 
            title="回看天数：用于计算注意力分位数的历史窗口长度"
          >
            Lookback Days
          </span>
          <input 
            className="px-2 py-1 bg-background border rounded" 
            type="number" 
            value={params.lookbackDays}
            onChange={e => updateParam('lookbackDays', Number(e.target.value))}
          />
        </label>

        <label className="flex flex-col gap-1 cursor-help">
          <span 
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" 
            title="注意力阈值（分位数）：触发买入信号的强度标准"
          >
            Threshold (Quantile)
          </span>
          <input 
            className="px-2 py-1 bg-background border rounded" 
            type="number" 
            step="0.05" 
            min={0} 
            max={1}
            value={params.attentionQuantile}
            onChange={e => updateParam('attentionQuantile', Number(e.target.value))}
          />
        </label>

        <label className="flex flex-col gap-1 cursor-help">
          <span 
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" 
            title="最大日涨幅限制：超过此值不追高买入"
          >
            Max Daily Return
          </span>
          <input 
            className="px-2 py-1 bg-background border rounded" 
            type="number" 
            step="0.01"
            value={params.maxDailyReturn}
            onChange={e => updateParam('maxDailyReturn', Number(e.target.value))}
          />
        </label>

        <label className="flex flex-col gap-1 cursor-help">
          <span 
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" 
            title="持仓天数：信号触发后默认持有的交易日数量"
          >
            Holding Period
          </span>
          <input 
            className="px-2 py-1 bg-background border rounded" 
            type="number"
            value={params.holdingDays}
            onChange={e => updateParam('holdingDays', Number(e.target.value))}
          />
        </label>

        <label className="flex flex-col gap-1 cursor-help">
          <span 
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" 
            title="止损（%）：亏损达到该比例时强制平仓"
          >
            止损 (%)
          </span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            step="0.5"
            value={params.stopLossPct != null ? params.stopLossPct * 100 : ''}
            onChange={e => {
              const v = e.target.value;
              updateParam('stopLossPct', v === '' ? null : Number(v) / 100);
            }}
          />
        </label>

        <label className="flex flex-col gap-1 cursor-help">
          <span 
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" 
            title="止盈（%）：盈利达到该比例时强制平仓"
          >
            止盈 (%)
          </span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            step="0.5"
            value={params.takeProfitPct != null ? params.takeProfitPct * 100 : ''}
            onChange={e => {
              const v = e.target.value;
              updateParam('takeProfitPct', v === '' ? null : Number(v) / 100);
            }}
          />
        </label>

        <label className="flex flex-col gap-1 cursor-help">
          <span 
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" 
            title="最长持仓天数：超过这个天数强制平仓"
          >
            最长持仓
          </span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            value={params.maxHoldingDays ?? ''}
            onChange={e => {
              const v = e.target.value;
              updateParam('maxHoldingDays', v === '' ? null : Number(v));
            }}
          />
        </label>

        <label className="flex flex-col gap-1 cursor-help">
          <span 
            className="flex items-center gap-1 border-b border-dotted border-muted-foreground/50 w-fit" 
            title="仓位大小 (0-1)：每笔交易投入的资金比例"
          >
            仓位
          </span>
          <input
            className="px-2 py-1 bg-background border rounded"
            type="number"
            min={0}
            max={1}
            step="0.1"
            value={params.positionSize}
            onChange={e => updateParam('positionSize', Number(e.target.value))}
          />
        </label>

        <div className="flex items-end gap-2">
          <Button onClick={onRunSingle} disabled={loading}>
            {loading ? 'Running...' : 'Single Backtest'}
          </Button>
          <Button variant="outline" onClick={onRunMulti} disabled={loading}>
            {loading ? 'Running...' : 'Multi-Asset'}
          </Button>
        </div>
      </div>

      {/* 注意力信号源选择 */}
      <div className="flex flex-wrap items-center gap-3 rounded border bg-background p-3 text-sm">
        <span className="text-xs text-muted-foreground">注意力信号源</span>
        <div className="flex gap-2">
          {([
            { key: 'legacy' as AttentionSource, label: 'Legacy (加权新闻)' },
            { key: 'composite' as AttentionSource, label: 'Composite (多通道)' },
          ]).map(option => (
            <button
              key={option.key}
              type="button"
              onClick={() => updateParam('attentionSource', option.key)}
              className={`rounded border px-3 py-1 text-xs ${
                params.attentionSource === option.key
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background hover:bg-muted'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        <span className="text-xs text-muted-foreground">
          Composite 推荐用于多币种回测，基于新闻 + Google + Twitter 权重融合。
        </span>
      </div>

      {/* Regime 条件配置 */}
      <div className="rounded border bg-background p-3 space-y-3">
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              className="h-4 w-4"
              checked={attentionCondition.enabled}
              onChange={e => updateCondition('enabled', e.target.checked)}
            />
            <span className="font-medium">使用 Attention Regime 条件</span>
          </label>
          <span className="text-[10px] text-muted-foreground">
            （研究用途 — Regime-Driven Preset）
          </span>
        </div>

        {attentionCondition.enabled && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Attention 源</span>
              <select
                className="px-2 py-1 bg-background border rounded text-sm"
                value={attentionCondition.source}
                onChange={e => updateCondition('source', e.target.value as AttentionConditionSource)}
              >
                <option value="composite">Composite</option>
                <option value="news_channel">News Channel</option>
              </select>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Regime</span>
              <select
                className="px-2 py-1 bg-background border rounded text-sm"
                value={attentionCondition.regime}
                onChange={e => updateCondition('regime', e.target.value as AttentionRegime)}
              >
                <option value="low">Low (0-33%)</option>
                <option value="mid">Mid (33-66%)</option>
                <option value="high">High (66-100%)</option>
                <option value="custom">Custom</option>
              </select>
            </label>

            {attentionCondition.regime === 'custom' && (
              <>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground">Lower Quantile</span>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    className="px-2 py-1 bg-background border rounded"
                    value={attentionCondition.lowerQuantile}
                    onChange={e => updateCondition('lowerQuantile', Number(e.target.value))}
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground">Upper Quantile</span>
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.05}
                    className="px-2 py-1 bg-background border rounded"
                    value={attentionCondition.upperQuantile}
                    onChange={e => updateCondition('upperQuantile', Number(e.target.value))}
                  />
                </label>
              </>
            )}

            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Lookback Days</span>
              <input
                type="number"
                min={1}
                className="px-2 py-1 bg-background border rounded"
                value={attentionCondition.lookbackDays}
                onChange={e => updateCondition('lookbackDays', Number(e.target.value))}
              />
            </label>
          </div>
        )}
      </div>
    </div>
  );
}
