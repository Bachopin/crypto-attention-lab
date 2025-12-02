"use client";

import React, { useState, useCallback } from 'react';
import { attentionService } from '@/lib/services';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info } from 'lucide-react';

interface Props {
  defaultSymbols?: string[];
}

type AttentionSource = 'composite' | 'news_channel';
type SplitMethod = 'tercile' | 'quartile';

interface RegimeStats {
  avg_return: number;
  pos_ratio: number;
  sample_count: number;
}

interface Regime {
  name: string;
  stats: Record<string, RegimeStats>;
  is_extreme?: boolean;
  description?: string;
  quantile_range?: [number, number];
}

interface SymbolResult {
  regimes: Regime[];
  meta?: { error?: string };
}

interface AnalysisResult {
  results: Record<string, SymbolResult>;
  meta: {
    lookahead_days: number[];
  };
}

export default function AttentionRegimePanel({ defaultSymbols = ['ZEC','BTC','ETH'] }: Props) {
  const [symbolsInput, setSymbolsInput] = useState(defaultSymbols.join(','));
  const [lookaheadDaysInput, setLookaheadDaysInput] = useState('7,30');
  const [attentionSource, setAttentionSource] = useState<AttentionSource>('composite');
  const [splitMethod, setSplitMethod] = useState<SplitMethod>('tercile');
  
  // 手动状态管理
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Sync symbolsInput when defaultSymbols changes
  React.useEffect(() => {
    setSymbolsInput(defaultSymbols.join(','));
  }, [defaultSymbols]);

  // 使用 useCallback 并传入所有依赖项，确保参数变化时函数更新
  const runAnalysis = useCallback(async () => {
    const symbols = symbolsInput.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
    const lookahead_days = lookaheadDaysInput.split(',').map(s => Number(s.trim())).filter(v => !isNaN(v) && v > 0);
    
    if (!symbols.length) {
      setError(new Error('请提供至少一个 symbol'));
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await attentionService.getAttentionRegimeAnalysis(symbols, {
        lookaheadDays: lookahead_days,
        attentionSource,
        splitMethod,
      });
      
      // 转换格式以匹配组件期望
      setData({
        results: result.results as unknown as Record<string, SymbolResult>,
        meta: {
          lookahead_days: result.meta.lookaheadDays,
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [symbolsInput, lookaheadDaysInput, attentionSource, splitMethod]);

  const generateAnalysisReport = (regimes: Regime[], lookaheadDays: number[]) => {
    if (!regimes || regimes.length < 2) return null;
    
    const low = regimes[0];
    const high = regimes[regimes.length - 1];
    
    return (
      <div className="mt-3 p-3 bg-muted/50 rounded text-xs space-y-2 border border-border/50">
        <div className="font-semibold text-foreground flex items-center gap-2">
          <span>💡 智能分析报告</span>
          <span className="text-[10px] font-normal text-muted-foreground bg-background px-1.5 py-0.5 rounded border">基于历史数据统计</span>
        </div>
        {lookaheadDays.map(days => {
          const k = String(days);
          const lowStats = low.stats?.[k];
          const highStats = high.stats?.[k];
          
          if (!lowStats || !highStats) return null;
          
          const lowRet = lowStats.avg_return;
          const highRet = highStats.avg_return;
          const diff = highRet - lowRet;
          
          let conclusion = "";
          let colorClass = "text-muted-foreground";
          
          if (highRet > 0.01 && diff > 0.005) {
            conclusion = "存在显著的动量效应，高关注度往往伴随价格上涨，适合顺势交易。";
            colorClass = "text-green-500 dark:text-green-400";
          } else if (highRet < -0.01) {
             conclusion = "存在过热反转风险，高关注度后往往伴随价格回调，需警惕追高。";
             colorClass = "text-red-500 dark:text-red-400";
          } else if (highRet > 0 && diff < -0.005) {
             conclusion = "虽然平均收益为正，但不如低关注度时期（边际效用递减），性价比降低。";
             colorClass = "text-yellow-600 dark:text-yellow-400";
          } else if (Math.abs(highRet) < 0.005) {
             conclusion = "高关注度下价格波动无明显方向，可能处于震荡期。";
          } else {
             conclusion = "关注度对未来收益影响不明确，建议结合其他指标。";
          }

          return (
            <div key={k} className="flex flex-col sm:flex-row sm:gap-2">
              <span className="font-medium min-w-[60px] text-muted-foreground">{days}天展望:</span>
              <span className={colorClass}>
                高关注度下平均收益 <strong>{(highRet * 100).toFixed(2)}%</strong> (vs 低关注度 {(lowRet * 100).toFixed(2)}%)。
                {conclusion}
              </span>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <TooltipProvider>
    <div className="bg-card rounded-lg border p-4 space-y-4">
      <div className="flex items-center gap-2">
        <h3 className="text-lg font-semibold">Attention Regime Analysis</h3>
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="h-4 w-4 text-muted-foreground cursor-help" />
          </TooltipTrigger>
          <TooltipContent className="max-w-sm">
            <p className="font-medium mb-1">Attention Regime 分析</p>
            <p className="text-xs">将历史注意力分数按分位数划分为低/中/高热度区间，统计不同热度下未来收益的差异，验证注意力因子的有效性。</p>
            <p className="text-xs mt-1 text-muted-foreground">若高热度区间的平均收益显著高于低热度，说明存在「动量效应」；反之可能存在「过热反转」现象。</p>
          </TooltipContent>
        </Tooltip>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">Symbols (逗号分隔)</span>
          <input className="px-2 py-1 bg-background border rounded" value={symbolsInput} onChange={e => setSymbolsInput(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground">Lookahead Days</span>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-3 w-3 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p>前瞻天数：统计事件发生后 N 天的收益</p>
                <p className="text-xs mt-1 text-muted-foreground">可输入多个值用逗号分隔，如 7,30 表示同时看 7 天和 30 天后的表现</p>
              </TooltipContent>
            </Tooltip>
          </div>
          <input className="px-2 py-1 bg-background border rounded" value={lookaheadDaysInput} onChange={e => setLookaheadDaysInput(e.target.value)} />
        </label>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground">Attention Source</span>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-3 w-3 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p><strong>composite</strong>: 综合注意力分数，融合新闻、社交等多维度</p>
                <p className="mt-1"><strong>news_channel</strong>: 仅使用新闻渠道的注意力数据</p>
              </TooltipContent>
            </Tooltip>
          </div>
          <div className="flex gap-2">
            {(['composite','news_channel'] as const).map(src => (
              <button key={src} type="button" onClick={() => setAttentionSource(src)} className={`rounded border px-2 py-1 text-xs ${attentionSource === src ? 'bg-primary text-primary-foreground' : 'bg-background hover:bg-muted'}`}>{src}</button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1">
            <span className="text-xs text-muted-foreground">Split Method</span>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-3 w-3 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p><strong>tercile</strong>: 三分位（低/中/高），每组约33%样本</p>
                <p className="mt-1"><strong>quartile</strong>: 四分位（Q1/Q2/Q3/Q4），每组约25%样本</p>
                <p className="text-xs mt-1 text-muted-foreground">四分位可提供更细粒度的分析，但每组样本量减少</p>
              </TooltipContent>
            </Tooltip>
          </div>
          <div className="flex gap-2">
            {(['tercile','quartile'] as const).map(m => (
              <button key={m} type="button" onClick={() => setSplitMethod(m)} className={`rounded border px-2 py-1 text-xs ${splitMethod === m ? 'bg-primary text-primary-foreground' : 'bg-background hover:bg-muted'}`}>{m}</button>
            ))}
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-3">
        <Button onClick={() => runAnalysis()} disabled={loading}>{loading ? 'Running...' : 'Run Analysis'}</Button>
        {error && <div className="text-red-500 text-xs">{error.message}</div>}
      </div>

      {data && (
        <div className="overflow-auto text-xs">
          {Object.entries(data.results).map(([sym, symRes]: [string, SymbolResult]) => (
            <div key={sym} className="mb-4 rounded border bg-background p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-medium">{sym}</span>
                {symRes.meta?.error && <span className="text-red-500">{symRes.meta.error}</span>}
              </div>
              <table className="w-full">
                <thead className="text-muted-foreground">
                  <tr>
                    <th className="text-left py-1">
                      <div className="flex items-center gap-1">
                        Regime
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="h-3 w-3 cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent>热度区间名称（Low/Mid/High 或 Q1-Q4）</TooltipContent>
                        </Tooltip>
                      </div>
                    </th>
                    <th className="text-right py-1">
                      <div className="flex items-center justify-end gap-1">
                        Samples
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="h-3 w-3 cursor-help" />
                          </TooltipTrigger>
                          <TooltipContent>该热度区间包含的历史样本数量</TooltipContent>
                        </Tooltip>
                      </div>
                    </th>
                    {data.meta.lookahead_days.map(k => (
                      <th key={k} className="text-right py-1">
                        <div className="flex items-center justify-end gap-1">
                          Avg {k}d
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Info className="h-3 w-3 cursor-help" />
                            </TooltipTrigger>
                            <TooltipContent>{k}天后的平均收益率</TooltipContent>
                          </Tooltip>
                        </div>
                      </th>
                    ))}
                    {data.meta.lookahead_days.map(k => (
                      <th key={`pos-${k}`} className="text-right py-1">
                        <div className="flex items-center justify-end gap-1">
                          Pos {k}d
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Info className="h-3 w-3 cursor-help" />
                            </TooltipTrigger>
                            <TooltipContent>{k}天后收益为正的概率（胜率）</TooltipContent>
                          </Tooltip>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {symRes.regimes && symRes.regimes.map((regime: Regime, idx: number) => {
                    const firstStatKey = Object.keys(regime.stats)[0];
                    const sampleCount = firstStatKey ? regime.stats[firstStatKey].sample_count : 0;
                    const isExtreme = regime.is_extreme;
                    const totalRegimes = symRes.regimes.filter(r => !r.is_extreme).length;
                    
                    // 生成解释性描述
                    const getRegimeDescription = () => {
                      if (isExtreme) {
                        return "🔥 极端高热度 (Top 5%)：市场关注度最高的时刻，通常伴随重大事件";
                      }
                      
                      // 根据分组方法和位置生成描述
                      const normalRegimes = symRes.regimes.filter(r => !r.is_extreme);
                      const regimeIdx = normalRegimes.findIndex(r => r.name === regime.name);
                      
                      if (totalRegimes === 3) {
                        // Tercile
                        if (regimeIdx === 0) return "🧊 低热度区间：市场关注较少，波动通常较小";
                        if (regimeIdx === 1) return "📊 中热度区间：市场关注度适中，常态水平";
                        if (regimeIdx === 2) return "🔥 高热度区间：市场关注较高，波动可能增大";
                      } else if (totalRegimes === 4) {
                        // Quartile
                        if (regimeIdx === 0) return "🧊 最低热度 (0-25%)：市场极度冷淡，通常是震荡期";
                        if (regimeIdx === 1) return "❄️ 较低热度 (25-50%)：市场关注度偏低";
                        if (regimeIdx === 2) return "🌡️ 较高热度 (50-75%)：市场关注度升温";
                        if (regimeIdx === 3) return "🔥 最高热度 (75-100%)：市场高度关注，需警惕追高风险";
                      }
                      
                      return "";
                    };
                    
                    const description = getRegimeDescription();
                    const rangeText = regime.quantile_range 
                      ? `[${regime.quantile_range[0]?.toFixed(2) ?? '-'}, ${regime.quantile_range[1]?.toFixed(2) ?? '-'}]`
                      : '';
                    
                    return (
                      <tr 
                        key={regime.name} 
                        className={`border-t border-border/40 ${isExtreme ? 'bg-orange-500/10 dark:bg-orange-500/20' : ''}`}
                      >
                        <td className="py-1.5">
                          <div className="flex flex-col">
                            <div className="flex items-center gap-2">
                              <span className={`font-medium ${isExtreme ? 'text-orange-600 dark:text-orange-400' : ''}`}>
                                {regime.description || regime.name}
                              </span>
                              {rangeText && (
                                <span className="text-[10px] text-muted-foreground font-mono">
                                  {rangeText}
                                </span>
                              )}
                            </div>
                            {description && (
                              <span className="text-[10px] text-muted-foreground mt-0.5">
                                {description}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-1.5 text-right align-top">{sampleCount}</td>
                        {data.meta.lookahead_days.map(k => {
                          const stats = regime.stats[String(k)];
                          const avgReturn = stats?.avg_return;
                          const v = avgReturn != null ? (avgReturn * 100).toFixed(2) + '%' : '-';
                          const colorClass = avgReturn != null 
                            ? avgReturn > 0.01 ? 'text-green-600 dark:text-green-400' 
                            : avgReturn < -0.01 ? 'text-red-600 dark:text-red-400' 
                            : ''
                            : '';
                          return <td key={`avg-${k}`} className={`py-1.5 text-right align-top ${colorClass}`}>{v}</td>;
                        })}
                        {data.meta.lookahead_days.map(k => {
                          const stats = regime.stats[String(k)];
                          const posRatio = stats?.pos_ratio;
                          const v = posRatio != null ? (posRatio * 100).toFixed(1) + '%' : '-';
                          const colorClass = posRatio != null
                            ? posRatio > 0.55 ? 'text-green-600 dark:text-green-400'
                            : posRatio < 0.45 ? 'text-red-600 dark:text-red-400'
                            : ''
                            : '';
                          return <td key={`pos-${k}`} className={`py-1.5 text-right align-top ${colorClass}`}>{v}</td>;
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              
              {/* Analysis Report */}
              {symRes.regimes && generateAnalysisReport(symRes.regimes, data.meta.lookahead_days)}
            </div>
          ))}
        </div>
      )}
    </div>
    </TooltipProvider>
  );
}
