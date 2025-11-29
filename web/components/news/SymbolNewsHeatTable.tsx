import React, { useMemo, useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { NewsItem } from '@/lib/api';
import { ArrowUpDown } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface SymbolNewsHeatTableProps {
  news: NewsItem[];
  onSymbolSelect: (symbol: string) => void;
  selectedSymbol: string;
}

interface SymbolStats {
  symbol: string;
  newsCount: number;
  weightedAttention: number;
  avgSentiment: number;
}

export function SymbolNewsHeatTable({ news, onSymbolSelect, selectedSymbol }: SymbolNewsHeatTableProps) {
  const [sortConfig, setSortConfig] = useState<{ key: keyof SymbolStats; direction: 'asc' | 'desc' }>({
    key: 'weightedAttention',
    direction: 'desc',
  });

  const symbolStats = useMemo(() => {
    const statsMap = new Map<string, { count: number; attention: number; sentimentSum: number }>();

    news.forEach(item => {
      if (!item.symbols) return;
      
      // Split symbols by comma and trim
      const symbols = item.symbols.split(',').map(s => s.trim()).filter(s => s);
      
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

    const result: SymbolStats[] = Array.from(statsMap.entries()).map(([symbol, data]) => ({
      symbol,
      newsCount: data.count,
      weightedAttention: data.attention,
      avgSentiment: data.count > 0 ? data.sentimentSum / data.count : 0,
    }));

    return result;
  }, [news]);

  const sortedStats = useMemo(() => {
    const sorted = [...symbolStats];
    sorted.sort((a, b) => {
      if (a[sortConfig.key] < b[sortConfig.key]) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (a[sortConfig.key] > b[sortConfig.key]) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });
    return sorted;
  }, [symbolStats, sortConfig]);

  const handleSort = (key: keyof SymbolStats) => {
    setSortConfig(current => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }));
  };

  return (
    <Card className="mb-6">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Symbol Heatmap</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="max-h-[300px] overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[100px]">Symbol</TableHead>
                <TableHead>
                  <Button variant="ghost" onClick={() => handleSort('newsCount')} className="h-8 flex items-center gap-1">
                    News Count
                    <ArrowUpDown className="h-3 w-3" />
                  </Button>
                </TableHead>
                <TableHead>
                  <Button variant="ghost" onClick={() => handleSort('weightedAttention')} className="h-8 flex items-center gap-1">
                    Weighted Attention
                    <ArrowUpDown className="h-3 w-3" />
                  </Button>
                </TableHead>
                <TableHead>
                  <Button variant="ghost" onClick={() => handleSort('avgSentiment')} className="h-8 flex items-center gap-1">
                    Avg Sentiment
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
                  <TableCell className="font-medium">{stat.symbol}</TableCell>
                  <TableCell>{stat.newsCount}</TableCell>
                  <TableCell>{stat.weightedAttention.toFixed(2)}</TableCell>
                  <TableCell className={stat.avgSentiment > 0 ? 'text-green-500' : stat.avgSentiment < 0 ? 'text-red-500' : ''}>
                    {stat.avgSentiment.toFixed(2)}
                  </TableCell>
                </TableRow>
              ))}
              {sortedStats.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No symbol data found in current news selection
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
