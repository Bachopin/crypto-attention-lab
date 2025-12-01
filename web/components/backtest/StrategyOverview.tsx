/**
 * 策略概览表格组件
 * 
 * 展示所有保存的策略及其表现摘要
 */

import React, { useMemo } from 'react';
import type { BacktestSummary, EquityPoint } from '@/types/models/backtest';
import { backtestService } from '@/lib/services';

interface StrategyOverviewProps {
  presetNames: string[];
  summaries: Record<string, BacktestSummary>;
  equities: Record<string, EquityPoint[]>;
  selectedComparePresets: string[];
  onToggleCompare: (name: string) => void;
  onLoadPreset: (name: string) => void;
}

export function StrategyOverview({
  presetNames,
  summaries,
  equities,
  selectedComparePresets,
  onToggleCompare,
  onLoadPreset,
}: StrategyOverviewProps) {
  const rows = useMemo(() => {
    return presetNames
      .map(name => ({ name, summary: summaries[name] }))
      .filter(row => !!row.summary)
      .sort((a, b) => (b.summary!.cumulativeReturn - a.summary!.cumulativeReturn));
  }, [presetNames, summaries]);

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
                    disabled={!selectedComparePresets.includes(name) && selectedComparePresets.length >= 3}
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
                  {summary?.attentionCondition && (
                    <span className="ml-1 text-[10px] font-mono text-muted-foreground/70">
                      [{backtestService.formatConditionSummary(summary.attentionCondition)}]
                    </span>
                  )}
                  {!equities[name]?.length && (
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      （需先运行回测）
                    </span>
                  )}
                </td>
                <td className="py-1 text-right">{summary?.totalTrades ?? 0}</td>
                <td className="py-1 text-right">{summary?.winRate?.toFixed(1) ?? 0}%</td>
                <td className={`py-1 text-right ${(summary?.cumulativeReturn ?? 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {((summary?.cumulativeReturn ?? 0) * 100).toFixed(2)}%
                </td>
                <td className="py-1 text-right text-red-600 dark:text-red-400">
                  {((summary?.maxDrawdown ?? 0) * 100).toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
