/**
 * 权益曲线图表组件
 * 
 * 支持单条和多条曲线对比展示
 */

import React, { useMemo } from 'react';
import type { EquityPoint } from '@/types/models/backtest';

interface EquityCurveProps {
  title: string;
  points: EquityPoint[];
  subtitle?: string;
  height?: number;
  className?: string;
}

export function EquityCurve({ 
  title, 
  points, 
  subtitle, 
  height = 96,
  className = '' 
}: EquityCurveProps) {
  const { path, minEquity, maxEquity } = useMemo(() => {
    if (!points.length) return { path: '', minEquity: 0, maxEquity: 0 };
    
    const values = points.map(p => p.equity);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const width = 100;
    const chartHeight = 40;
    const stepX = points.length > 1 ? width / (points.length - 1) : 0;
    
    const d = points
      .map((p, idx) => {
        const x = idx * stepX;
        const y = chartHeight - ((p.equity - min) / span) * chartHeight;
        return `${idx === 0 ? 'M' : 'L'}${x},${y}`;
      })
      .join(' ');
    
    return { path: d, minEquity: min, maxEquity: max };
  }, [points]);

  if (!points.length || !path) return null;

  return (
    <div className={`space-y-1 rounded border bg-background p-3 ${className}`}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{title}</span>
        <span className="flex items-center gap-2">
          {subtitle && (
            <span className="text-[10px] uppercase tracking-wide">{subtitle}</span>
          )}
          <span>{`${minEquity.toFixed(2)} → ${maxEquity.toFixed(2)}`}</span>
        </span>
      </div>
      <svg viewBox="0 0 100 40" className="w-full" style={{ height }}>
        <path 
          d={path} 
          fill="none" 
          strokeWidth={1.5} 
          className="stroke-primary" 
        />
      </svg>
    </div>
  );
}

interface MultiEquityCurveProps {
  series: { name: string; points: EquityPoint[]; color?: string }[];
  title?: string;
  height?: number;
  className?: string;
}

export function MultiEquityCurve({ 
  series, 
  title = '多策略权益曲线对比',
  height = 112,
  className = '' 
}: MultiEquityCurveProps) {
  const colors = ['stroke-primary', 'stroke-emerald-400', 'stroke-amber-400', 'stroke-pink-400'];

  const { paths, minEquity, maxEquity } = useMemo(() => {
    if (!series.length) {
      return { paths: [], minEquity: 0, maxEquity: 0 };
    }

    const allValues = series.flatMap(s => s.points.map(p => p.equity));
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const span = max - min || 1;
    const width = 100;
    const chartHeight = 40;

    const built = series.map((s, idx) => {
      const pts = s.points;
      const stepX = pts.length > 1 ? width / (pts.length - 1) : 0;
      const d = pts
        .map((p, i) => {
          const x = i * stepX;
          const y = chartHeight - ((p.equity - min) / span) * chartHeight;
          return `${i === 0 ? 'M' : 'L'}${x},${y}`;
        })
        .join(' ');
      return { 
        name: s.name, 
        d, 
        colorClass: s.color || colors[idx % colors.length] 
      };
    });

    return { paths: built, minEquity: min, maxEquity: max };
  }, [series, colors]);

  if (!series.length) {
    return (
      <div className="rounded border border-dashed bg-muted/40 p-3 text-xs text-muted-foreground">
        选择的策略暂无权益曲线数据
      </div>
    );
  }

  return (
    <div className={`space-y-2 rounded border bg-background p-3 ${className}`}>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{title}</span>
        <span>{`${minEquity.toFixed(2)} → ${maxEquity.toFixed(2)}`}</span>
      </div>
      <svg viewBox="0 0 100 40" className="w-full" style={{ height }}>
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
