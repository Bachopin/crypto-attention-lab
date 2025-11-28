"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchNodeInfluence, NodeInfluenceItem } from "@/lib/api";
import { Separator } from "@/components/ui/separator";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

type SortKey = "ir" | "mean_excess_return" | "hit_rate";

export default function NodeInfluencePage() {
  const [symbol, setSymbol] = useState<string>("ZEC");
  const [minEvents, setMinEvents] = useState<number>(10);
  const [sortBy, setSortBy] = useState<SortKey>("ir");
  const [limit, setLimit] = useState<number>(100);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<NodeInfluenceItem[]>([]);

  const params = useMemo(() => ({ symbol, min_events: minEvents, sort_by: sortBy, limit }), [symbol, minEvents, sortBy, limit]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchNodeInfluence({ symbol, min_events: minEvents, sort_by: sortBy, limit });
      setData(res);
    } catch (e: any) {
      setError(e?.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [params]);

  return (
    <div className="container mx-auto px-4 py-6">
      <div className="flex items-center gap-4 mb-4">
        <Link href="/">
          <Button variant="ghost" size="sm" className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            返回主页
          </Button>
        </Link>
      </div>
      <h1 className="text-2xl font-semibold">节点带货能力因子</h1>
      <p className="text-sm text-muted-foreground mt-1">按 IR/平均收益/命中率排序，筛选最小样本数</p>
      <Separator className="my-4" />

      <Card className="p-4 mb-4">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <label className="block text-sm mb-1">标的 Symbol</label>
            <input
              className="w-full border rounded px-2 py-1"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.trim().toUpperCase())}
              placeholder="如 ZEC"
            />
          </div>
          <div>
            <label className="block text-sm mb-1">最小样本数</label>
            <input
              type="number"
              className="w-full border rounded px-2 py-1"
              value={minEvents}
              min={0}
              onChange={(e) => setMinEvents(Number(e.target.value))}
            />
          </div>
          <div>
            <label className="block text-sm mb-1">排序字段</label>
            <select
              className="w-full border rounded px-2 py-1"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortKey)}
            >
              <option value="ir">IR</option>
              <option value="mean_excess_return">平均收益</option>
              <option value="hit_rate">命中率</option>
            </select>
          </div>
          <div>
            <label className="block text-sm mb-1">数量上限</label>
            <input
              type="number"
              className="w-full border rounded px-2 py-1"
              value={limit}
              min={1}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
          </div>
          <div className="flex items-end">
            <button
              className="border rounded px-3 py-1 hover:bg-muted"
              onClick={load}
              disabled={loading}
            >
              {loading ? "加载中..." : "刷新"}
            </button>
          </div>
        </div>
      </Card>

      {error && (
        <div className="text-red-600 text-sm mb-3">{error}</div>
      )}

      <Tabs defaultValue="table">
        <TabsList>
          <TabsTrigger value="table">表格视图</TabsTrigger>
          <TabsTrigger value="raw">原始 JSON</TabsTrigger>
        </TabsList>
        <TabsContent value="table">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th className="px-2 py-2">Node</th>
                  <th className="px-2 py-2">样本数</th>
                  <th className="px-2 py-2">平均收益</th>
                  <th className="px-2 py-2">命中率</th>
                  <th className="px-2 py-2">IR</th>
                  <th className="px-2 py-2">参数</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row) => (
                  <tr key={`${row.symbol}-${row.node_id}`} className="border-t">
                    <td className="px-2 py-2 font-mono">{row.node_id}</td>
                    <td className="px-2 py-2">{row.n_events}</td>
                    <td className="px-2 py-2">{row.mean_excess_return.toFixed(4)}</td>
                    <td className="px-2 py-2">{(row.hit_rate * 100).toFixed(1)}%</td>
                    <td className="px-2 py-2">{row.ir.toFixed(3)}</td>
                    <td className="px-2 py-2 text-muted-foreground">
                      {row.lookahead} / {row.lookback_days}d
                    </td>
                  </tr>
                ))}
                {data.length === 0 && !loading && (
                  <tr>
                    <td className="px-2 py-4" colSpan={6}>暂无数据</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </TabsContent>
        <TabsContent value="raw">
          <pre className="text-xs bg-muted p-3 rounded overflow-x-auto">
            {JSON.stringify(data, null, 2)}
          </pre>
        </TabsContent>
      </Tabs>
    </div>
  );
}
