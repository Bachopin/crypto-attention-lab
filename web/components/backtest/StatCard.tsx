/**
 * 回测统计卡片组件
 */

import React from 'react';
import { InfoIcon } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  tooltip?: string;
  variant?: 'default' | 'positive' | 'negative';
}

export function StatCard({ label, value, tooltip, variant = 'default' }: StatCardProps) {
  const valueClass = variant === 'positive' 
    ? 'text-green-600 dark:text-green-400' 
    : variant === 'negative' 
      ? 'text-red-600 dark:text-red-400' 
      : '';

  const content = (
    <div className="bg-background rounded border p-3">
      <div className="text-xs text-muted-foreground flex items-center gap-1">
        {label}
        {tooltip && <InfoIcon className="w-3 h-3 text-muted-foreground/50" />}
      </div>
      <div className={`text-base font-semibold ${valueClass}`}>{value}</div>
    </div>
  );

  if (tooltip) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            {content}
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-xs text-xs">
            <p>{tooltip}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return content;
}

interface StatGridProps {
  stats: {
    label: string;
    value: React.ReactNode;
    tooltip?: string;
    variant?: 'default' | 'positive' | 'negative';
  }[];
  columns?: number;
}

export function StatGrid({ stats, columns = 5 }: StatGridProps) {
  return (
    <div 
      className="grid gap-3" 
      style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
    >
      {stats.map((stat, i) => (
        <StatCard key={i} {...stat} />
      ))}
    </div>
  );
}
