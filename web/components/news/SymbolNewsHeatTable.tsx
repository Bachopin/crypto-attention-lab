import React, { useMemo, useState, useEffect } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { NewsItem, TopCoin, fetchTopCoins } from '@/lib/api';
import { ArrowUpDown, Info, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from '@/components/ui/badge';

interface SymbolNewsHeatTableProps {
  news: NewsItem[];
  onSymbolSelect: (symbol: string) => void;
  selectedSymbol: string;
}

interface SymbolStats {
  symbol: string;
  name?: string;
  rank?: number | null;
  marketCap?: number | null;
  priceChange24h?: number | null;
  newsCount: number;
  weightedAttention: number;
  attentionPercent: number;
  avgSentiment: number;
  isTop100: boolean;
}

export function SymbolNewsHeatTable({ news, onSymbolSelect, selectedSymbol }: SymbolNewsHeatTableProps) {
  const [sortConfig, setSortConfig] = useState<{ key: keyof SymbolStats; direction: 'asc' | 'desc' }>({
    key: 'attentionPercent',
    direction: 'desc',
  });
  const [topCoins, setTopCoins] = useState<TopCoin[]>([]);
  const [loadingTopCoins, setLoadingTopCoins] = useState(false);
  const [showOnlyTop100, setShowOnlyTop100] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  // 获取 CoinGecko 市值前100
  useEffect(() => {
    const loadTopCoins = async () => {
      setLoadingTopCoins(true);
      try {
        const response = await fetchTopCoins(100);
        setTopCoins(response.coins);
        setLastUpdated(response.updated_at);
      } catch (e) {
        console.error('Failed to fetch top coins:', e);
      } finally {
        setLoadingTopCoins(false);
      }
    };
    loadTopCoins();
  }, []);

  // 创建 top100 symbol 集合和映射表
  const top100Map = useMemo(() => {
    const map = new Map<string, TopCoin>();
    topCoins.forEach(coin => {
      map.set(coin.symbol.toUpperCase(), coin);
    });
    return map;
  }, [topCoins]);

  const symbolStats = useMemo(() => {
    const statsMap = new Map<string, { count: number; attention: number; sentimentSum: number }>();

    // 从新闻中统计每个 symbol 的数据
    news.forEach(item => {
      if (!item.symbols) return;
      
      const symbols = item.symbols.split(',').map(s => s.trim().toUpperCase()).filter(s => s);
      
      symbols.forEach(sym => {
        if (!statsMap.has(sym)) {
          statsMap.set(sym, { count: 0, attention: 0, sentimentSum: 0 });
        }
        const entry = statsMap.get(sym)!;
        entry.count += 1;
        entry.attention += (item.source_weight || 1);
        entry.sentimentSum += (item.sentiment_score || 0);
      });
    });

    // 对于 top100 中没有新闻的币种，也添加进来（显示为 0）
    topCoins.forEach(coin => {
      const sym = coin.symbol.toUpperCase();
      if (!statsMap.has(sym)) {
        statsMap.set(sym, { count: 0, attention: 0, sentimentSum: 0 });
      }
    });

    // 计算总 attention（仅计算有新闻的）
    let totalAttention = 0;
    statsMap.forEach(data => {
      totalAttention += data.attention;
    });

    const result: SymbolStats[] = Array.from(statsMap.entries()).map(([symbol, data]) => {
      const coinInfo = top100Map.get(symbol);
      return {
        symbol,
        name: coinInfo?.name,
        rank: coinInfo?.market_cap_rank,
        marketCap: coinInfo?.market_cap,
        priceChange24h: coinInfo?.price_change_24h,
        newsCount: data.count,
        weightedAttention: data.attention,
        attentionPercent: totalAttention > 0 ? (data.attention / totalAttention) * 100 : 0,
        avgSentiment: data.count > 0 ? data.sentimentSum / data.count : 0,
        isTop100: top100Map.has(symbol),
      };
    });

    return result;
  }, [news, topCoins, top100Map]);

  // 过滤和排序
  const sortedStats = useMemo(() => {
    let filtered = symbolStats;
    
    // 如果开启 top100 过滤，只显示 top100 中的币种
    if (showOnlyTop100) {
      filtered = symbolStats.filter(s => s.isTop100);
    }
    
    const sorted = [...filtered];
    sorted.sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];
      
      // 处理 null/undefined
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return sortConfig.direction === 'asc' ? -1 : 1;
      if (bVal == null) return sortConfig.direction === 'asc' ? 1 : -1;
      
      if (aVal < bVal) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (aVal > bVal) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
    return sorted;
  }, [symbolStats, sortConfig, showOnlyTop100]);

  const handleSort = (key: keyof SymbolStats) => {
    setSortConfig(current => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }));
  };

  // 刷新 top100 数据
  const refreshTopCoins = async () => {
    setLoadingTopCoins(true);
    try {
      const response = await fetchTopCoins(100);
      setTopCoins(response.coins);
      setLastUpdated(response.updated_at);
    } catch (e) {
      console.error('Failed to refresh top coins:', e);
    } finally {
      setLoadingTopCoins(false);
    }
  };

  const top100Count = symbolStats.filter(s => s.isTop100).length;
  const newsSymbolCount = symbolStats.filter(s => s.newsCount > 0).length;

  return (
    <TooltipProvider>
    <Card className="mb-6">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm font-medium">Symbol Heatmap</CardTitle>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-4 w-4 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p>显示新闻中提及的币种及其关注度分布</p>
                <p className="text-xs mt-1 text-muted-foreground">
                  数据来源：新闻 symbols 标签 + CoinGecko 市值前100
                </p>
              </TooltipContent>
            </Tooltip>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">
              {newsSymbolCount} 有新闻 / {top100Count} Top100
            </Badge>
            <Button 
              variant={showOnlyTop100 ? "default" : "outline"} 
              size="sm" 
              onClick={() => setShowOnlyTop100(!showOnlyTop100)}
              className="text-xs h-7"
            >
              {showOnlyTop100 ? "显示全部" : "仅 Top100"}
            </Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  onClick={refreshTopCoins}
                  disabled={loadingTopCoins}
                  className="h-7 w-7 p-0"
                >
                  <RefreshCw className={`h-3 w-3 ${loadingTopCoins ? 'animate-spin' : ''}`} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>刷新市值排行数据</p>
                {lastUpdated && (
                  <p className="text-xs text-muted-foreground">
                    上次更新: {new Date(lastUpdated).toLocaleString()}
                  </p>
                )}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="max-h-[400px] overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[60px]">
                  <Button variant="ghost" onClick={() => handleSort('rank')} className="h-8 flex items-center gap-1 text-xs">
                    Rank
                    <ArrowUpDown className="h-3 w-3" />
                  </Button>
                </TableHead>
                <TableHead className="w-[100px]">Symbol</TableHead>
                <TableHead>
                  <Button variant="ghost" onClick={() => handleSort('newsCount')} className="h-8 flex items-center gap-1">
                    News
                    <ArrowUpDown className="h-3 w-3" />
                  </Button>
                </TableHead>
                <TableHead>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" onClick={() => handleSort('attentionPercent')} className="h-8 flex items-center gap-1">
                      Attention %
                      <ArrowUpDown className="h-3 w-3" />
                    </Button>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-3 w-3 text-muted-foreground cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <p>加权注意力占比 = 该币种的新闻加权总和 ÷ 所有币种加权总和 × 100%</p>
                        <p className="text-xs mt-1 text-muted-foreground">权重来自新闻源 source_weight，反映该币种在当前时间段内获得的相对关注度</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </TableHead>
                <TableHead>
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" onClick={() => handleSort('avgSentiment')} className="h-8 flex items-center gap-1">
                      Sentiment
                      <ArrowUpDown className="h-3 w-3" />
                    </Button>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="h-3 w-3 text-muted-foreground cursor-help" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <p>平均情绪分数 = 该币种所有新闻的 sentiment_score 平均值</p>
                        <p className="text-xs mt-1 text-muted-foreground">范围 -1 到 1，正值表示偏多（绿色），负值表示偏空（红色），接近 0 表示中性</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                </TableHead>
                <TableHead>
                  <Button variant="ghost" onClick={() => handleSort('priceChange24h')} className="h-8 flex items-center gap-1">
                    24h %
                    <ArrowUpDown className="h-3 w-3" />
                  </Button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedStats.map((stat) => (
                <TableRow 
                  key={stat.symbol} 
                  className={`cursor-pointer hover:bg-muted/50 ${selectedSymbol === stat.symbol ? 'bg-muted' : ''}`}
                  onClick={() => onSymbolSelect(stat.symbol === selectedSymbol ? 'ALL' : stat.symbol)}
                >
                  <TableCell className="text-xs text-muted-foreground">
                    {stat.rank ? `#${stat.rank}` : '-'}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium">{stat.symbol}</span>
                      {stat.name && (
                        <span className="text-xs text-muted-foreground truncate max-w-[80px]" title={stat.name}>
                          {stat.name}
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    {stat.newsCount > 0 ? (
                      <Badge variant="secondary" className="text-xs">
                        {stat.newsCount}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground text-xs">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {stat.attentionPercent > 0 ? (
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-muted rounded-full h-2">
                          <div 
                            className="bg-primary h-2 rounded-full" 
                            style={{ width: `${Math.min(stat.attentionPercent * 2, 100)}%` }}
                          />
                        </div>
                        <span className="text-sm">{stat.attentionPercent.toFixed(1)}%</span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground text-xs">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {stat.newsCount > 0 ? (
                      <span className={
                        stat.avgSentiment > 0.05 ? 'text-green-500' : 
                        stat.avgSentiment < -0.05 ? 'text-red-500' : 
                        'text-muted-foreground'
                      }>
                        {stat.avgSentiment.toFixed(2)}
                      </span>
                    ) : (
                      <span className="text-muted-foreground text-xs">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {stat.priceChange24h != null ? (
                      <div className={`flex items-center gap-1 ${
                        stat.priceChange24h > 0 ? 'text-green-500' : 
                        stat.priceChange24h < 0 ? 'text-red-500' : ''
                      }`}>
                        {stat.priceChange24h > 0 ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : stat.priceChange24h < 0 ? (
                          <TrendingDown className="h-3 w-3" />
                        ) : null}
                        <span className="text-sm">{stat.priceChange24h.toFixed(2)}%</span>
                      </div>
                    ) : (
                      <span className="text-muted-foreground text-xs">-</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {sortedStats.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    {loadingTopCoins ? 'Loading market data...' : 'No symbol data found'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
    </TooltipProvider>
  );
}
