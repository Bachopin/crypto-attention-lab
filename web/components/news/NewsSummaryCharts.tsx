import React, { useMemo, useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  ReferenceLine
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { NewsItem, NewsTrendPoint, fetchNewsTrend } from '@/lib/api';
import { format, parseISO, subDays, subHours } from 'date-fns';

interface NewsSummaryChartsProps {
  news: NewsItem[];
  timeRange: '24h' | '7d' | '14d' | '30d';
}

const LANGUAGE_MAP: Record<string, string> = {
  'en': 'English',
  'zh': 'Chinese',
  'ko': 'Korean',
  'ja': 'Japanese',
  'ru': 'Russian',
  'es': 'Spanish',
  'fr': 'French',
  'de': 'German',
  'it': 'Italian',
  'pt': 'Portuguese',
  'tr': 'Turkish',
  'vi': 'Vietnamese',
  'unknown': 'Unknown'
};

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d'];

export function NewsSummaryCharts({ news, timeRange }: NewsSummaryChartsProps) {
  // 使用聚合 API 获取趋势数据
  const [trendData, setTrendData] = useState<NewsTrendPoint[]>([]);
  const [trendLoading, setTrendLoading] = useState(false);

  useEffect(() => {
    const loadTrend = async () => {
      setTrendLoading(true);
      try {
        const now = new Date();
        let start: Date;
        let interval: '1h' | '1d' = '1d';

        if (timeRange === '24h') {
          start = subHours(now, 24);
          interval = '1h';
        } else if (timeRange === '7d') {
          start = subDays(now, 7);
        } else if (timeRange === '14d') {
          start = subDays(now, 14);
        } else {
          start = subDays(now, 30);
        }

        const data = await fetchNewsTrend({
          symbol: 'ALL',
          start: start.toISOString(),
          end: now.toISOString(),
          interval
        });
        setTrendData(data);
      } catch (e) {
        console.error('Failed to fetch news trend:', e);
        setTrendData([]);
      } finally {
        setTrendLoading(false);
      }
    };
    loadTrend();
  }, [timeRange]);

  // 格式化趋势数据用于图表
  const timeData = useMemo(() => {
    return trendData.map(point => ({
      time: timeRange === '24h' 
        ? format(parseISO(point.time), 'HH:mm')
        : format(parseISO(point.time), 'MM-dd'),
      count: point.count,
      attention_score: point.attention_score,
      z_score: point.z_score
    }));
  }, [trendData, timeRange]);

  const dateRangeLabel = useMemo(() => {
    if (!trendData.length) return '';
    const times = trendData.map(p => new Date(p.time).getTime());
    const min = new Date(Math.min(...times));
    const max = new Date(Math.max(...times));
    return `${format(min, 'MM-dd')} to ${format(max, 'MM-dd')}`;
  }, [trendData]);

  const sourceData = useMemo(() => {
    const counts = new Map<string, number>();
    news.forEach(item => {
      const source = item.source || 'Unknown';
      counts.set(source, (counts.get(source) || 0) + 1);
    });

    return Array.from(counts.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10); // Top 10
  }, [news]);

  const languageData = useMemo(() => {
    const counts = new Map<string, number>();
    news.forEach(item => {
      let lang = item.language || 'Unknown';
      if (lang === 'None' || !lang) lang = 'Unknown';
      lang = lang.toLowerCase();
      
      // Map code to name
      const name = LANGUAGE_MAP[lang] || (lang.length === 2 ? lang.toUpperCase() : lang.charAt(0).toUpperCase() + lang.slice(1));
      
      counts.set(name, (counts.get(name) || 0) + 1);
    });

    return Array.from(counts.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value);
  }, [news]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {/* Time Trend */}
      <Card className="col-span-1 md:col-span-3 lg:col-span-1">
        <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
            News & Attention Trend
            {dateRangeLabel && <span className="ml-2 text-xs font-normal text-muted-foreground">({dateRangeLabel})</span>}
            <span className="ml-2 text-xs font-normal text-muted-foreground cursor-help" title="Attention Score 基于 Z-Score 标准化(0-100)：50=平均水平，80+=高热度，20-=低热度。与回测策略信号一致。">ⓘ</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[200px] w-full">
            {trendLoading ? (
              <div className="h-full flex items-center justify-center text-muted-foreground">
                Loading trend data...
              </div>
            ) : timeData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-muted-foreground">
                No data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeData}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="time" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="left" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="right" orientation="right" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
                    itemStyle={{ color: 'hsl(var(--foreground))' }}
                    formatter={(value: number, name: string) => {
                      if (name === 'Attention Score') return [`${value.toFixed(1)} (${value >= 80 ? '🔥高' : value >= 60 ? '📈较高' : value >= 40 ? '📊正常' : '📉较低'})`, name];
                      return [value, name];
                    }}
                  />
                  <Legend />
                  {/* 参考线：80分为高热度阈值，50分为平均线 */}
                  <ReferenceLine yAxisId="right" y={80} stroke="#ef4444" strokeDasharray="3 3" label={{ value: '高热度', position: 'right', fontSize: 10, fill: '#ef4444' }} />
                  <ReferenceLine yAxisId="right" y={50} stroke="#6b7280" strokeDasharray="3 3" opacity={0.5} />
                  <Line yAxisId="left" type="monotone" dataKey="count" stroke="#8884d8" name="News Count" dot={false} strokeWidth={2} />
                  <Line yAxisId="right" type="monotone" dataKey="attention_score" stroke="#82ca9d" name="Attention Score" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Source Distribution */}
      <Card className="col-span-1 md:col-span-3 lg:col-span-1">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Top Sources</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[200px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sourceData} layout="vertical" margin={{ left: 40 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" width={80} fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip 
                  cursor={{fill: 'transparent'}}
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
                  itemStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Bar dataKey="value" fill="#8884d8" radius={[0, 4, 4, 0]} name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Language Distribution */}
      <Card className="col-span-1 md:col-span-3 lg:col-span-1">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">Language Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[200px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={languageData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={80}
                  fill="#8884d8"
                  paddingAngle={5}
                  dataKey="value"
                >
                  {languageData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
                  itemStyle={{ color: 'hsl(var(--foreground))' }}
                />
                <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ fontSize: '10px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
