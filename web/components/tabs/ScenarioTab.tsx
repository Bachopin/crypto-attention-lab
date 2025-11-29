'use client';

import { useState, useEffect } from 'react';
import { fetchStateScenarios, StateScenarioResponse, ScenarioSummary } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, RefreshCw, Activity } from 'lucide-react';
import ScenarioPanel from '@/components/ScenarioPanel';

type Props = {
  defaultSymbol?: string;
};

// Helper to format percentage
const fmtPct = (val: number | undefined | null) => {
  if (val === undefined || val === null) return '-';
  return `${(val * 100).toFixed(2)}%`;
};

// Helper to get color for return
const getReturnColor = (val: number | undefined | null) => {
  if (val === undefined || val === null) return 'text-muted-foreground';
  return val > 0 ? 'text-green-500' : val < 0 ? 'text-red-500' : 'text-muted-foreground';
};

// Helper to find dominant scenario
const getDominantScenario = (scenarios: ScenarioSummary[]) => {
  if (!scenarios || scenarios.length === 0) return null;
  return scenarios.reduce((prev, current) => (prev.probability > current.probability) ? prev : current);
};

export function ScenarioTab({ defaultSymbol = 'ZEC' }: Props) {
  const [primarySymbol, setPrimarySymbol] = useState<string>(defaultSymbol);
  const [compareSymbolsInput, setCompareSymbolsInput] = useState<string>('BTC, ETH, SOL');
  const [timeframe, setTimeframe] = useState<'1d' | '4h'>('1d');
  const [windowDays, setWindowDays] = useState<string>('30');
  const [topK, setTopK] = useState<string>('100');

  const [compareData, setCompareData] = useState<StateScenarioResponse[]>([]);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Primary symbol data is handled by ScenarioPanel, but we need to handle comparison here

  async function handleLoadCompare() {
    const symbols = compareSymbolsInput.split(',').map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
    if (symbols.length === 0) return;

    setLoadingCompare(true);
    setCompareError(null);
    setCompareData([]);

    try {
      const results: StateScenarioResponse[] = [];
      for (const sym of symbols) {
        try {
          const res = await fetchStateScenarios({
            symbol: sym,
            timeframe,
            window_days: parseInt(windowDays),
            top_k: parseInt(topK),
          });
          results.push(res);
        } catch (e) {
          console.error(`Failed to load scenario for ${sym}`, e);
          // Continue with other symbols
        }
      }
      setCompareData(results);
    } catch (e: any) {
      setCompareError(e.message ?? 'Failed to load compare scenarios');
    } finally {
      setLoadingCompare(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* 顶部说明 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            情景分析（Scenario Analysis）
          </CardTitle>
          <CardDescription>
            基于历史上 Attention + Price + Volume 状态相似的样本，对未来 3/7/30 天可能出现的走势模式进行统计性推演。
            这些结果用于研究与趋势判断，不构成投资建议。
          </CardDescription>
        </CardHeader>
      </Card>

      {/* 上：控制面板 + 当前标的情景卡片 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          {/* 控制面板 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">分析参数</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="primarySymbol">主分析代币</Label>
                <Input 
                  id="primarySymbol" 
                  value={primarySymbol} 
                  onChange={(e) => setPrimarySymbol(e.target.value.toUpperCase())} 
                  placeholder="e.g. ZEC"
                />
              </div>
              
              <div className="space-y-2">
                <Label>时间周期</Label>
                <Select value={timeframe} onValueChange={(v: '1d'|'4h') => setTimeframe(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1d">Daily (1D)</SelectItem>
                    <SelectItem value="4h">4 Hours (4H)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>回溯窗口 (Days)</Label>
                <Select value={windowDays} onValueChange={setWindowDays}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="14">14 Days</SelectItem>
                    <SelectItem value="30">30 Days</SelectItem>
                    <SelectItem value="60">60 Days</SelectItem>
                    <SelectItem value="90">90 Days</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>相似样本数 (Top K)</Label>
                <Select value={topK} onValueChange={setTopK}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="50">50</SelectItem>
                    <SelectItem value="100">100</SelectItem>
                    <SelectItem value="200">200</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          {/* 复用 ScenarioPanel 作为主展示 */}
          <ScenarioPanel 
            symbol={primarySymbol}
            timeframe={timeframe}
            windowDays={parseInt(windowDays)}
            topK={parseInt(topK)}
          />
        </div>
      </div>

      {/* 下：多标对比表 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="space-y-1">
            <CardTitle>多标情景对比</CardTitle>
            <CardDescription>对比不同代币在当前参数下的情景特征</CardDescription>
          </div>
          <div className="flex items-center gap-2">
             <Input 
                className="w-64"
                value={compareSymbolsInput}
                onChange={(e) => setCompareSymbolsInput(e.target.value)}
                placeholder="BTC, ETH, SOL..."
             />
            <Button
              onClick={handleLoadCompare}
              size="sm"
              disabled={loadingCompare}
              className="gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${loadingCompare ? 'animate-spin' : ''}`} />
              {loadingCompare ? '分析中...' : '运行对比'}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {compareError && (
             <div className="p-4 mb-4 text-sm text-red-500 bg-red-50 dark:bg-red-950/30 rounded-md">
               {compareError}
             </div>
          )}
          
          {compareData.length > 0 ? (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Symbol</TableHead>
                    <TableHead>Dominant Scenario</TableHead>
                    <TableHead>Probability</TableHead>
                    <TableHead className="text-right">Exp. Return (7D)</TableHead>
                    <TableHead className="text-right">Max Drawdown (7D)</TableHead>
                    <TableHead className="text-right">Volatility (30D)</TableHead>
                    <TableHead>Risk Profile</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {compareData.map((data) => {
                    const symbol = data.target.symbol;
                    const dominant = getDominantScenario(data.scenarios);
                    const volatility = data.target.features['volatility_30d'];
                    
                    // Determine risk profile based on volatility and drawdown
                    let riskProfile = 'Moderate';
                    if (volatility > 0.05 || (dominant?.max_drawdown_7d || 0) < -0.1) riskProfile = 'High';
                    if (volatility < 0.02 && (dominant?.max_drawdown_7d || 0) > -0.05) riskProfile = 'Low';

                    return (
                      <TableRow key={symbol}>
                        <TableCell className="font-medium">{symbol}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {dominant?.label === 'trend_up' && <TrendingUp className="w-4 h-4 text-green-500" />}
                            {dominant?.label === 'trend_down' && <TrendingDown className="w-4 h-4 text-red-500" />}
                            {dominant?.label === 'sideways' && <Minus className="w-4 h-4 text-yellow-500" />}
                            {dominant?.label === 'crash' && <AlertTriangle className="w-4 h-4 text-red-600" />}
                            <span className="capitalize">{dominant?.label.replace('_', ' ')}</span>
                          </div>
                        </TableCell>
                        <TableCell>{fmtPct(dominant?.probability)}</TableCell>
                        <TableCell className={`text-right ${getReturnColor(dominant?.avg_return_7d)}`}>
                          {fmtPct(dominant?.avg_return_7d)}
                        </TableCell>
                        <TableCell className="text-right text-red-500">
                          {fmtPct(dominant?.max_drawdown_7d)}
                        </TableCell>
                        <TableCell className="text-right">
                          {fmtPct(volatility)}
                        </TableCell>
                        <TableCell>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            riskProfile === 'High' ? 'bg-red-500/10 text-red-500' :
                            riskProfile === 'Low' ? 'bg-green-500/10 text-green-500' :
                            'bg-yellow-500/10 text-yellow-500'
                          }`}>
                            {riskProfile}
                          </span>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              输入代币列表并点击“运行对比”以查看多标的分析结果
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
