import React, { useMemo } from 'react';
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
  Line
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { NewsItem } from '@/lib/api';
import { format, parseISO, startOfHour, startOfDay } from 'date-fns';

interface NewsSummaryChartsProps {
  news: NewsItem[];
  timeRange: '24h' | '7d' | '30d';
}

export function NewsSummaryCharts({ news, timeRange }: NewsSummaryChartsProps) {
  const timeData = useMemo(() => {
    if (!news.length) return [];

    const grouped = new Map<string, { time: string; count: number; attention: number }>();

    news.forEach(item => {
      const date = parseISO(item.datetime);
      let key: string;
      let displayTime: string;

      if (timeRange === '24h') {
        const hour = startOfHour(date);
        key = hour.toISOString();
        displayTime = format(hour, 'HH:mm');
      } else {
        const day = startOfDay(date);
        key = day.toISOString();
        displayTime = format(day, 'MM-dd');
      }

      if (!grouped.has(key)) {
        grouped.set(key, { time: displayTime, count: 0, attention: 0 });
      }
      const entry = grouped.get(key)!;
      entry.count += 1;
      entry.attention += (item.source_weight || 1);
    });

    // Sort by time
    return Array.from(grouped.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(entry => entry[1]);
  }, [news, timeRange]);

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
      counts.set(lang, (counts.get(lang) || 0) + 1);
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
          <CardTitle className="text-sm font-medium">News & Attention Trend</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[200px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeData}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="time" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis yAxisId="left" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis yAxisId="right" orientation="right" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
                />
                <Legend />
                <Line yAxisId="left" type="monotone" dataKey="count" stroke="#8884d8" name="News Count" dot={false} strokeWidth={2} />
                <Line yAxisId="right" type="monotone" dataKey="attention" stroke="#82ca9d" name="Attention" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
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
              <BarChart data={languageData}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} vertical={false} />
                <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  cursor={{fill: 'transparent'}}
                  contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
                />
                <Bar dataKey="value" fill="#82ca9d" radius={[4, 4, 0, 0]} name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
