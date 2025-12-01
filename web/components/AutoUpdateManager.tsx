'use client';

/**
 * AutoUpdateManagerV2 - 重构后的自动更新管理器
 * 
 * 使用服务层 + hooks 模式重构：
 * 1. 数据获取通过 autoUpdateService
 * 2. 状态管理通过 useAsync / useAsyncCallback
 * 3. 统一的加载/错误状态处理
 */

import React, { useState, useCallback, useEffect } from 'react';
import { useAsync, useAsyncCallback } from '@/lib/hooks';
import { autoUpdateService, type SymbolUpdateStatus } from '@/lib/services';
import { AsyncBoundary, LoadingSpinner, ErrorState } from '@/components/ui/async-boundary';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { RefreshCw, Plus, Play, Pause, Trash2, Check, X } from 'lucide-react';

interface AutoUpdateManagerV2Props {
  /** 更新后的回调 */
  onUpdate?: () => void;
}

export function AutoUpdateManagerV2({ onUpdate }: AutoUpdateManagerV2Props) {
  const [newSymbol, setNewSymbol] = useState('');

  // 获取状态
  const {
    data: status,
    loading,
    error,
    refresh: refreshStatus,
  } = useAsync(
    () => autoUpdateService.getAutoUpdateStatus(),
    [],
    { staleTime: 30000 } // 30秒内不重复请求
  );

  // 操作 hooks
  const enableAction = useAsyncCallback(
    (symbol: string) => autoUpdateService.enableAutoUpdate([symbol])
  );
  
  const disableAction = useAsyncCallback(
    (symbol: string) => autoUpdateService.disableAutoUpdate([symbol])
  );
  
  const removeAction = useAsyncCallback(
    (symbol: string) => autoUpdateService.removeSymbols([symbol])
  );
  
  const triggerAction = useAsyncCallback(
    (symbol: string) => autoUpdateService.triggerUpdate([symbol])
  );
  
  const addAction = useAsyncCallback(
    (symbol: string) => autoUpdateService.addSymbol(symbol)
  );

  // 操作后刷新
  const handleAfterAction = useCallback(() => {
    refreshStatus();
    onUpdate?.();
  }, [refreshStatus, onUpdate]);

  // 定时刷新状态
  useEffect(() => {
    const interval = setInterval(refreshStatus, 30000);
    return () => clearInterval(interval);
  }, [refreshStatus]);

  // 添加新代币
  const handleAddSymbol = async () => {
    if (!newSymbol.trim()) return;
    const result = await addAction.execute(newSymbol);
    if (result?.success) {
      setNewSymbol('');
      handleAfterAction();
      if (result.invalid && result.invalid.length > 0) {
        alert(`以下代币在 Binance 上不存在: ${result.invalid.join(', ')}`);
      }
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            实时价格跟踪管理
            <span className="text-sm font-normal text-muted-foreground">
              (每 10 分钟自动更新)
            </span>
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={refreshStatus}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </CardTitle>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* 添加新代币 */}
        <div className="flex gap-2 pb-4 border-b">
          <Input
            placeholder="添加新标的 (如 BTC, ETH)"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
            onKeyPress={(e) => e.key === 'Enter' && handleAddSymbol()}
            className="flex-1"
          />
          <Button
            onClick={handleAddSymbol}
            disabled={!newSymbol.trim() || addAction.loading}
          >
            {addAction.loading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Plus className="w-4 h-4" />
            )}
            <span className="ml-2">添加</span>
          </Button>
        </div>

        {/* 添加错误提示 */}
        {addAction.error && (
          <div className="text-sm text-destructive bg-destructive/10 p-2 rounded">
            {addAction.error.message}
          </div>
        )}

        {/* 代币列表 */}
        <AsyncBoundary
          loading={loading}
          error={error}
          data={status}
          onRetry={refreshStatus}
          loadingFallback={<LoadingSpinner message="加载中..." size="sm" />}
          emptyFallback={
            <p className="text-muted-foreground text-center py-4">暂无跟踪标的</p>
          }
          isEmpty={(s) => s.symbols.length === 0}
        >
          {(statusData) => (
            <div className="space-y-2">
              {statusData.symbols.map((sym) => (
                <SymbolRow
                  key={sym.symbol}
                  status={sym}
                  onEnable={async () => {
                    await enableAction.execute(sym.symbol);
                    handleAfterAction();
                  }}
                  onDisable={async () => {
                    await disableAction.execute(sym.symbol);
                    handleAfterAction();
                  }}
                  onRemove={async () => {
                    if (confirm(`确定要移除 ${sym.symbol} 吗？`)) {
                      await removeAction.execute(sym.symbol);
                      handleAfterAction();
                    }
                  }}
                  onTrigger={async () => {
                    await triggerAction.execute(sym.symbol);
                    handleAfterAction();
                  }}
                  loading={
                    enableAction.loading ||
                    disableAction.loading ||
                    removeAction.loading ||
                    triggerAction.loading
                  }
                />
              ))}
            </div>
          )}
        </AsyncBoundary>
      </CardContent>
    </Card>
  );
}

// ==================== 子组件 ====================

interface SymbolRowProps {
  status: SymbolUpdateStatus;
  onEnable: () => Promise<void>;
  onDisable: () => Promise<void>;
  onRemove: () => Promise<void>;
  onTrigger: () => Promise<void>;
  loading: boolean;
}

function SymbolRow({
  status,
  onEnable,
  onDisable,
  onRemove,
  onTrigger,
  loading,
}: SymbolRowProps) {
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleAction = async (action: string, fn: () => Promise<void>) => {
    setActionLoading(action);
    try {
      await fn();
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors">
      <div className="flex items-center gap-3">
        {/* 状态指示器 */}
        <div className={`w-3 h-3 rounded-full ${
          status.autoUpdate ? 'bg-green-500 animate-pulse' : 'bg-gray-300'
        }`} />

        {/* 代币信息 */}
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold">{status.symbol}</span>
            <span className={`text-xs px-2 py-0.5 rounded ${
              status.autoUpdate
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
            }`}>
              {status.autoUpdate ? '自动更新' : '已暂停'}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            上次更新: {autoUpdateService.formatLastUpdateTime(status.lastUpdate)}
          </p>
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-2">
        {status.autoUpdate ? (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleAction('trigger', onTrigger)}
              disabled={loading || actionLoading !== null}
            >
              {actionLoading === 'trigger' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              <span className="ml-1.5">立即更新</span>
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleAction('disable', onDisable)}
              disabled={loading || actionLoading !== null}
              className="text-destructive hover:text-destructive"
            >
              {actionLoading === 'disable' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Pause className="w-4 h-4" />
              )}
              <span className="ml-1.5">停止</span>
            </Button>
          </>
        ) : (
          <>
            <Button
              size="sm"
              onClick={() => handleAction('enable', onEnable)}
              disabled={loading || actionLoading !== null}
            >
              {actionLoading === 'enable' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              <span className="ml-1.5">启动</span>
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleAction('remove', onRemove)}
              disabled={loading || actionLoading !== null}
              className="text-muted-foreground hover:text-destructive"
            >
              {actionLoading === 'remove' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4" />
              )}
              <span className="ml-1.5">移除</span>
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

export default AutoUpdateManagerV2;
