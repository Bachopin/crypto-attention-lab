/**
 * 交易记录表格组件
 */

import React from 'react';
import type { Trade } from '@/types/models/backtest';

interface TradeTableProps {
  trades: Trade[];
  maxHeight?: number;
}

export function TradeTable({ trades, maxHeight = 400 }: TradeTableProps) {
  if (!trades.length) {
    return (
      <div className="rounded-md border border-dashed border-muted-foreground/40 bg-muted/40 p-3 text-xs text-muted-foreground">
        在当前参数下没有产生交易，可以尝试降低 attention_quantile 或放宽 max_daily_return。
      </div>
    );
  }

  return (
    <div className="overflow-auto" style={{ maxHeight }}>
      <table className="w-full text-sm">
        <thead className="text-muted-foreground sticky top-0 bg-card z-10">
          <tr>
            <th className="text-left py-2">Entry</th>
            <th className="text-left py-2">Exit</th>
            <th className="text-right py-2">Entry Px</th>
            <th className="text-right py-2">Exit Px</th>
            <th className="text-right py-2">Return</th>
            {trades[0]?.reason && <th className="text-left py-2">Reason</th>}
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={i} className="border-t border-border/50">
              <td className="py-1">
                {new Date(t.entryDate).toLocaleDateString()}
              </td>
              <td className="py-1">
                {new Date(t.exitDate).toLocaleDateString()}
              </td>
              <td className="text-right">{t.entryPrice.toFixed(2)}</td>
              <td className="text-right">{t.exitPrice.toFixed(2)}</td>
              <td className={`text-right ${t.returnPct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {(t.returnPct * 100).toFixed(2)}%
              </td>
              {t.reason && (
                <td className="py-1 text-muted-foreground text-xs">{t.reason}</td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
