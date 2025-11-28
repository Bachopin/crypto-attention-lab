'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';

interface SymbolStatus {
  symbol: string;
  auto_update: boolean;
  last_update: string | null;
  is_active: boolean;
}

interface AutoUpdateManagerProps {
  apiBaseUrl?: string;
  onUpdate?: () => void; // 触发数据刷新的回调
}

export default function AutoUpdateManager({ 
  apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
  onUpdate 
}: AutoUpdateManagerProps) {
  const [symbols, setSymbols] = useState<SymbolStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [newSymbol, setNewSymbol] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // 加载标的状态
  const loadStatus = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/auto-update/status`);
      const data = await res.json();
      setSymbols(data.symbols);
    } catch (err) {
      console.error('Failed to load auto-update status:', err);
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  // 启用自动更新
  const enableAutoUpdate = async (symbol: string) => {
    setActionLoading(symbol);
    try {
      const res = await fetch(`${apiBaseUrl}/api/auto-update/enable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: [symbol] })
      });
      
      if (res.ok) {
        await loadStatus();
        onUpdate?.(); // 触发父组件数据刷新
      }
    } catch (err) {
      console.error('Failed to enable auto-update:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // 禁用自动更新
  const disableAutoUpdate = async (symbol: string) => {
    setActionLoading(symbol);
    try {
      const res = await fetch(`${apiBaseUrl}/api/auto-update/disable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: [symbol] })
      });
      
      if (res.ok) {
        await loadStatus();
        onUpdate?.();
      }
    } catch (err) {
      console.error('Failed to disable auto-update:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // 手动触发更新
  const triggerUpdate = async (symbol: string) => {
    setActionLoading(`trigger-${symbol}`);
    try {
      const res = await fetch(`${apiBaseUrl}/api/auto-update/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: [symbol] })
      });
      
      if (res.ok) {
        await loadStatus();
        onUpdate?.();
      }
    } catch (err) {
      console.error('Failed to trigger update:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // 添加新标的
  const addSymbol = async () => {
    if (!newSymbol.trim()) return;
    
    setActionLoading('add-new');
    try {
      const res = await fetch(`${apiBaseUrl}/api/auto-update/enable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: [newSymbol.toUpperCase()] })
      });
      
      if (res.ok) {
        setNewSymbol('');
        await loadStatus();
        onUpdate?.();
      }
    } catch (err) {
      console.error('Failed to add symbol:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // 格式化时间
  const formatTime = (isoString: string | null) => {
    if (!isoString) return '从未更新';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins} 分钟前`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)} 小时前`;
    return `${Math.floor(diffMins / 1440)} 天前`;
  };

  useEffect(() => {
    loadStatus();
    // 每 30 秒刷新状态
    const interval = setInterval(loadStatus, 30000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>实时价格跟踪管理</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">加载中...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          实时价格跟踪管理
          <span className="text-sm font-normal text-gray-500">
            (每 2 分钟自动更新)
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 添加新标的 */}
        <div className="flex gap-2 pb-4 border-b">
          <input
            type="text"
            placeholder="添加新标的 (如 BTC, ETH)"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
            onKeyPress={(e) => e.key === 'Enter' && addSymbol()}
            className="flex-1 px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary bg-card text-foreground placeholder:text-muted-foreground border-border"
          />
          <Button 
            onClick={addSymbol}
            disabled={!newSymbol.trim() || actionLoading === 'add-new'}
          >
            {actionLoading === 'add-new' ? '添加中...' : '添加'}
          </Button>
        </div>

        {/* 标的列表 */}
        <div className="space-y-2">
          {symbols.length === 0 ? (
            <p className="text-gray-500 text-center py-4">暂无跟踪标的</p>
          ) : (
            symbols.map((sym) => (
              <div
                key={sym.symbol}
                className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted bg-card border-border"
              >
                <div className="flex items-center gap-3 flex-1">
                  {/* 状态指示器 */}
                  <div className="relative">
                    {sym.auto_update ? (
                      <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                    ) : (
                      <div className="w-3 h-3 bg-gray-300 rounded-full" />
                    )}
                  </div>

                  {/* 标的信息 */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-foreground">{sym.symbol}</span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          sym.auto_update
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {sym.auto_update ? '自动更新' : '已暂停'}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      上次更新: {formatTime(sym.last_update)}
                    </p>
                  </div>
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-2">
                  {sym.auto_update ? (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => triggerUpdate(sym.symbol)}
                        disabled={actionLoading === `trigger-${sym.symbol}`}
                      >
                        {actionLoading === `trigger-${sym.symbol}` ? '更新中...' : '立即更新'}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => disableAutoUpdate(sym.symbol)}
                        disabled={actionLoading === sym.symbol}
                        className="text-red-600 hover:text-red-700"
                      >
                        {actionLoading === sym.symbol ? '停止中...' : '停止'}
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => enableAutoUpdate(sym.symbol)}
                      disabled={actionLoading === sym.symbol}
                    >
                      {actionLoading === sym.symbol ? '启动中...' : '启动'}
                    </Button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
