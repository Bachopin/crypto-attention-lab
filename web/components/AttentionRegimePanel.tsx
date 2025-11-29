"use client";

import React, { useState } from 'react';
import { fetchAttentionRegimeAnalysis, AttentionRegimeResponse } from '@/lib/api';
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

export default function AttentionRegimePanel({ defaultSymbols = ['ZEC','BTC','ETH'] }: Props) {
  const [symbolsInput, setSymbolsInput] = useState(defaultSymbols.join(','));
  const [lookaheadDaysInput, setLookaheadDaysInput] = useState('7,30');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AttentionRegimeResponse | null>(null);
  const [attentionSource, setAttentionSource] = useState<'composite' | 'news_channel'>('composite');
  const [splitMethod, setSplitMethod] = useState<'tercile' | 'quartile'>('tercile');

  async function runAnalysis() {
    setLoading(true); setError(null); setData(null);
    try {
      const symbols = symbolsInput.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
      const lookahead_days = lookaheadDaysInput.split(',').map(s => Number(s.trim())).filter(v => !isNaN(v) && v > 0);
      if (!symbols.length) throw new Error('请提供至少一个 symbol');
      const res = await fetchAttentionRegimeAnalysis({ symbols, lookahead_days, attention_source: attentionSource, split_method: splitMethod });
      setData(res);
    } catch (e: any) {
      setError(e?.message || '分析失败');
    } finally {
      setLoading(false);
    }
  }

  const generateAnalysisReport = (regimes: any[], lookaheadDays: number[]) => {
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
          const lowStats = low.stats[k];
          const highStats = high.stats[k];
          
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
        <Button onClick={runAnalysis} disabled={loading}>{loading ? 'Running...' : 'Run Analysis'}</Button>
        {error && <div className="text-red-500 text-xs">{error}</div>}
      </div>

      {data && (
        <div className="overflow-auto text-xs">
          {Object.entries(data.results).map(([sym, symRes]: [string, any]) => (
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
                  {symRes.regimes && symRes.regimes.map((regime: any) => {
                    // Get sample count from the first available stats
                    const firstStatKey = Object.keys(regime.stats)[0];
                    const sampleCount = firstStatKey ? regime.stats[firstStatKey].sample_count : 0;
                    
                    return (
                      <tr key={regime.name} className="border-t border-border/40">
                        <td className="py-1 font-medium">{regime.name}</td>
                        <td className="py-1 text-right">{sampleCount}</td>
                        {data.meta.lookahead_days.map(k => {
                          const stats = regime.stats[String(k)];
                          const v = stats?.avg_return != null ? (stats.avg_return * 100).toFixed(2) + '%' : '-';
                          return <td key={`avg-${k}`} className="py-1 text-right">{v}</td>;
                        })}
                        {data.meta.lookahead_days.map(k => {
                          const stats = regime.stats[String(k)];
                          const v = stats?.pos_ratio != null ? (stats.pos_ratio * 100).toFixed(1) + '%' : '-';
                          return <td key={`pos-${k}`} className="py-1 text-right">{v}</td>;
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