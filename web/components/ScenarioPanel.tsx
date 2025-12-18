"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { fetchStateScenarios, StateScenarioResponse, ScenarioSummary } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  AlertTriangle, 
  Minus,
  RefreshCw,
  Info,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface Props {
  symbol: string;
  timeframe?: string;
  windowDays?: number;
  topK?: number;
  compact?: boolean;
  maxScenarios?: number;
}

// 情景标签对应的图标和颜色
const SCENARIO_CONFIG: Record<string, {
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
}> = {
  trend_up: {
    icon: <TrendingUp className="w-5 h-5" />,
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-950/30',
    borderColor: 'border-green-200 dark:border-green-800',
    label: '趋势上行',
  },
  trend_down: {
    icon: <TrendingDown className="w-5 h-5" />,
    color: 'text-red-600 dark:text-red-400',
    bgColor: 'bg-red-50 dark:bg-red-950/30',
    borderColor: 'border-red-200 dark:border-red-800',
    label: '趋势下行',
  },
  spike_and_revert: {
    icon: <Activity className="w-5 h-5" />,
    color: 'text-yellow-600 dark:text-yellow-400',
    bgColor: 'bg-yellow-50 dark:bg-yellow-950/30',
    borderColor: 'border-yellow-200 dark:border-yellow-800',
    label: '冲高回落',
  },
  crash: {
    icon: <AlertTriangle className="w-5 h-5" />,
    color: 'text-red-700 dark:text-red-500',
    bgColor: 'bg-red-100 dark:bg-red-950/50',
    borderColor: 'border-red-300 dark:border-red-700',
    label: '急剧下跌',
  },
  sideways: {
    icon: <Minus className="w-5 h-5" />,
    color: 'text-gray-600 dark:text-gray-400',
    bgColor: 'bg-gray-50 dark:bg-gray-800/50',
    borderColor: 'border-gray-200 dark:border-gray-700',
    label: '横盘震荡',
  },
};

// 格式化百分比
function formatPercent(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '-';
  const pct = value * 100;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(decimals)}%`;
}

// 获取颜色类
function getReturnColorClass(value: number | null | undefined): string {
  if (value == null) return 'text-muted-foreground';
  if (value > 0.01) return 'text-green-600 dark:text-green-400';
  if (value < -0.01) return 'text-red-600 dark:text-red-400';
  return 'text-muted-foreground';
}

// 获取回撤颜色类
function getDrawdownColorClass(value: number | null | undefined): string {
  if (value == null) return 'text-muted-foreground';
  if (value < -0.10) return 'text-red-600 dark:text-red-400';
  if (value < -0.05) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-muted-foreground';
}

// 情景卡片组件
function ScenarioCard({ scenario }: { scenario: ScenarioSummary }) {
  const [expanded, setExpanded] = useState(false);
  const config = SCENARIO_CONFIG[scenario.label] || SCENARIO_CONFIG.sideways;

  return (
    <div
      className={`rounded-lg border ${config.borderColor} ${config.bgColor} p-3 sm:p-4 transition-all hover:shadow-md min-w-0 flex flex-col`}
    >
      {/* 头部：标签和概率 */}
      <div className="flex items-center justify-between mb-2 sm:mb-3 gap-2 flex-shrink-0">
        <div className="flex items-center gap-1.5 sm:gap-2 min-w-0 flex-1">
          <span className={`${config.color} flex-shrink-0`}>{config.icon}</span>
          <span className={`font-semibold ${config.color} text-sm sm:text-base`}>{config.label}</span>
        </div>
        <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
          <span className="text-lg sm:text-2xl font-bold whitespace-nowrap">{(scenario.probability * 100).toFixed(0)}%</span>
          <span className="text-xs text-muted-foreground hidden sm:inline whitespace-nowrap">概率</span>
        </div>
      </div>

      {/* 样本数 */}
      <div className="text-xs text-muted-foreground mb-2 sm:mb-3 flex-shrink-0">
        基于 {scenario.sample_count} 个历史相似样本
      </div>

      {/* 收益统计 */}
      <div className="grid grid-cols-3 gap-1.5 sm:gap-2 mb-2 sm:mb-3 flex-shrink-0">
        <div className="text-center min-w-[50px] px-1">
          <div className="text-[10px] sm:text-xs text-muted-foreground mb-0.5 sm:mb-1 leading-tight whitespace-nowrap">3日</div>
          <div className={`text-[10px] sm:text-xs font-semibold ${getReturnColorClass(scenario.avg_return_3d)} leading-tight whitespace-nowrap`}>
            {formatPercent(scenario.avg_return_3d)}
          </div>
        </div>
        <div className="text-center min-w-[50px] px-1">
          <div className="text-[10px] sm:text-xs text-muted-foreground mb-0.5 sm:mb-1 leading-tight whitespace-nowrap">7日</div>
          <div className={`text-[10px] sm:text-xs font-semibold ${getReturnColorClass(scenario.avg_return_7d)} leading-tight whitespace-nowrap`}>
            {formatPercent(scenario.avg_return_7d)}
          </div>
        </div>
        <div className="text-center min-w-[50px] px-1">
          <div className="text-[10px] sm:text-xs text-muted-foreground mb-0.5 sm:mb-1 leading-tight whitespace-nowrap">30日</div>
          <div className={`text-[10px] sm:text-xs font-semibold ${getReturnColorClass(scenario.avg_return_30d)} leading-tight whitespace-nowrap`}>
            {formatPercent(scenario.avg_return_30d)}
          </div>
        </div>
      </div>

      {/* 展开/收起按钮 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors w-full justify-center mt-auto pt-2 flex-shrink-0"
      >
        {expanded ? (
          <>
            <ChevronUp className="w-3 h-3" /> 收起详情
          </>
        ) : (
          <>
            <ChevronDown className="w-3 h-3" /> 展开详情
          </>
        )}
      </button>

      {/* 详情（展开时显示） */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-border/50 space-y-3">
          {/* 最大回撤 */}
          <div className="grid grid-cols-2 gap-2">
            <div className="text-center">
              <div className="text-xs text-muted-foreground mb-1">7日最大回撤</div>
              <div className={`text-sm font-semibold ${getDrawdownColorClass(scenario.max_drawdown_7d)}`}>
                {formatPercent(scenario.max_drawdown_7d)}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs text-muted-foreground mb-1">30日最大回撤</div>
              <div className={`text-sm font-semibold ${getDrawdownColorClass(scenario.max_drawdown_30d)}`}>
                {formatPercent(scenario.max_drawdown_30d)}
              </div>
            </div>
          </div>

          {/* 描述 */}
          <p className="text-xs text-muted-foreground italic">
            {scenario.description}
          </p>
        </div>
      )}
    </div>
  );
}

// 状态摘要组件
function StateSummary({ target }: { target: StateScenarioResponse['target'] }) {
  const features = target.features;
  const rawStats = target.raw_stats;

  // 提取关键指标
  const compositeZ = features.att_composite_z ?? 0;
  const retWindow = features.ret_window ?? 0;
  const volWindow = features.vol_window ?? 0;
  const closePrice = rawStats.close_price ?? 0;
  const returnPct = rawStats.return_window_pct ?? 0;

  // 判断注意力状态
  let attentionStatus = '正常';
  let attentionColor = 'text-muted-foreground';
  if (compositeZ > 1.5) {
    attentionStatus = '高关注';
    attentionColor = 'text-red-500';
  } else if (compositeZ > 0.5) {
    attentionStatus = '偏高';
    attentionColor = 'text-yellow-500';
  } else if (compositeZ < -0.5) {
    attentionStatus = '偏低';
    attentionColor = 'text-blue-500';
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
      <div className="bg-muted/50 rounded-lg p-3">
        <div className="text-xs text-muted-foreground mb-1">当前价格</div>
        <div className="font-semibold">${closePrice.toFixed(2)}</div>
      </div>
      <div className="bg-muted/50 rounded-lg p-3">
        <div className="text-xs text-muted-foreground mb-1 cursor-help" title="过去 N 天的累计收益率，反映近期价格走势">{target.window_days}日收益 ⓘ</div>
        <div className={`font-semibold ${returnPct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
          {formatPercent(returnPct)}
        </div>
      </div>
      <div className="bg-muted/50 rounded-lg p-3">
        <div className="text-xs text-muted-foreground mb-1 cursor-help" title="注意力 Z 值：表示当前热度偏离平均多少个标准差。>1.5=高关注，<-0.5=偏低">注意力 Z 值 ⓘ</div>
        <div className={`font-semibold ${attentionColor}`}>
          {compositeZ.toFixed(2)} ({attentionStatus})
        </div>
      </div>
      <div className="bg-muted/50 rounded-lg p-3">
        <div className="text-xs text-muted-foreground mb-1 cursor-help" title="波动率状态：基于近期价格波动判断。高波动时风险较大，低波动可能预示突破">波动率 ⓘ</div>
        <div className="font-semibold">
          {volWindow > 1 ? '高波动' : volWindow < -1 ? '低波动' : '正常'}
        </div>
      </div>
    </div>
  );
}

export default function ScenarioPanel({ 
  symbol, 
  timeframe = '1d', 
  windowDays = 30, 
  topK = 100,
  compact = false,
  maxScenarios = 3
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<StateScenarioResponse | null>(null);

  const loadScenarios = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const res = await Promise.race([
        fetchStateScenarios({
          symbol,
          timeframe,
          window_days: windowDays,
          top_k: topK,
          max_history_days: 365,
        }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('请求超时，请稍后重试')), 60000))
      ]) as StateScenarioResponse;
      setData(res);
    } catch (e: any) {
      console.error('[ScenarioPanel] Error loading scenarios:', e);
      const msg = e?.message || '情景分析失败';
      if (msg.includes('No data available')) {
        setError(`代币 ${symbol} 暂无数据。请等待数据同步完成，或检查该代币是否在 Binance 上存在。`);
      } else if (msg.includes('超时')) {
        setError('请求超时，数据量较大正在计算中，请稍后重试或减少 topK 参数。');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe, windowDays, topK]);

  // 当任何关键参数变化时重新加载
  useEffect(() => {
    loadScenarios();
  }, [loadScenarios]);

  if (compact) {
    return (
      <div className="bg-muted/30 rounded-lg p-3 border border-border/50 h-full flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-medium flex items-center gap-2 cursor-help" title="基于当前市场状态（价格趋势、波动率、注意力）寻找历史相似时刻，统计这些时刻后的价格走势分布">
            <Activity className="w-4 h-4 text-primary" />
            Scenario Analysis
          </h4>
          <Button
            variant="ghost"
            size="sm"
            onClick={loadScenarios}
            disabled={loading}
            className="h-6 px-2 text-xs gap-1 hover:bg-background"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            {loading ? '分析中...' : '刷新'}
          </Button>
        </div>

        <div className="flex-1 min-h-[200px]">
          {/* 加载状态 */}
          {loading && !data && (
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-2">
                <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-muted-foreground">分析中...</p>
              </div>
            </div>
          )}

          {/* 错误状态 */}
          {error && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <AlertTriangle className="w-8 h-8 text-red-500 mx-auto mb-2" />
                <p className="text-xs text-red-500 mb-2">{error}</p>
                <Button variant="outline" size="sm" onClick={loadScenarios} className="h-7 text-xs">
                  重试
                </Button>
              </div>
            </div>
          )}

          {/* 数据展示 */}
          {data && !loading && (
            <div className="h-full flex flex-col">
              {data.scenarios.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 gap-3 h-full auto-rows-fr">
                  {data.scenarios.slice(0, maxScenarios).map((scenario) => (
                    <ScenarioCard key={scenario.label} scenario={scenario} />
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground text-xs">
                  暂无足够的历史数据进行情景分析
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 cursor-help" title="基于当前市场状态（价格趋势、波动率、注意力）寻找历史相似时刻，统计这些时刻后的价格走势分布，提供客观参考">
              <Activity className="w-5 h-5 text-primary" />
              Scenario Analysis ⓘ
            </CardTitle>
            <CardDescription className="mt-1">
              基于历史相似 Attention 状态的未来情景统计推演
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadScenarios}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {loading ? '分析中...' : '刷新'}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* 提示信息 */}
        <div className="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800 text-xs">
          <Info className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
          <div className="text-blue-700 dark:text-blue-300">
            <strong>声明：</strong>本分析基于历史相似 Attention 状态的统计推演，仅供研究参考，
            不构成交易建议。过往表现不代表未来收益。
          </div>
        </div>

        {/* 加载状态 */}
        {loading && !data && (
          <div className="flex items-center justify-center h-48">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-3 border-primary border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-muted-foreground">正在分析历史相似状态...</p>
            </div>
          </div>
        )}

        {/* 错误状态 */}
        {error && (
          <div className="flex items-center justify-center h-48">
            <div className="text-center">
              <AlertTriangle className="w-10 h-10 text-red-500 mx-auto mb-2" />
              <p className="text-sm text-red-500">{error}</p>
              <Button variant="outline" size="sm" onClick={loadScenarios} className="mt-3">
                重试
              </Button>
            </div>
          </div>
        )}

        {/* 数据展示 */}
        {data && !loading && (
          <>
            {/* 当前状态摘要 */}
            <div>
              <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                <span className="text-muted-foreground">当前状态</span>
                <span className="text-xs bg-muted px-2 py-0.5 rounded">
                  {data.target.symbol} · {data.target.timeframe} · {data.target.window_days}日窗口
                </span>
              </h4>
              <StateSummary target={data.target} />
            </div>

            {/* 分析元数据 */}
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>相似样本: {data.meta.total_similar_samples}</span>
              <span>有效分析: {data.meta.valid_samples_analyzed}</span>
              <span>前瞻窗口: {data.meta.lookahead_days.join('/')}天</span>
            </div>

            {/* 情景卡片栈 */}
            {data.scenarios.length > 0 ? (
              <div>
                <h4 className="text-sm font-medium mb-3 text-muted-foreground">可能情景</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {data.scenarios.map((scenario, idx) => (
                    <ScenarioCard key={scenario.label} scenario={scenario} />
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <p>暂无足够的历史数据进行情景分析</p>
              </div>
            )}

            {/* 主要结论 */}
            {data.scenarios.length > 0 && (
              <div className="p-4 bg-muted/50 rounded-lg border border-border/50">
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  💡 主要发现
                </h4>
                <div className="text-sm text-muted-foreground space-y-1">
                  {(() => {
                    const topScenario = data.scenarios[0];
                    const config = SCENARIO_CONFIG[topScenario.label] || SCENARIO_CONFIG.sideways;
                    return (
                      <>
                        <p>
                          历史上类似 Attention 状态下，最可能出现的情景是
                          <span className={`font-semibold ${config.color}`}> {config.label} </span>
                          （{(topScenario.probability * 100).toFixed(0)}% 概率）。
                        </p>
                        {topScenario.avg_return_7d != null && (
                          <p>
                            该情景下 7 日平均收益为
                            <span className={`font-semibold ${getReturnColorClass(topScenario.avg_return_7d)}`}>
                              {' '}{formatPercent(topScenario.avg_return_7d)}
                            </span>
                            {topScenario.max_drawdown_7d != null && (
                              <>
                                ，最大回撤约
                                <span className={`font-semibold ${getDrawdownColorClass(topScenario.max_drawdown_7d)}`}>
                                  {' '}{formatPercent(topScenario.max_drawdown_7d)}
                                </span>
                              </>
                            )}。
                          </p>
                        )}
                      </>
                    );
                  })()}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
