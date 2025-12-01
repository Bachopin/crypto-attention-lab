/**
 * 自动更新服务层
 * 
 * 负责自动更新状态管理、触发更新等功能
 */

import { buildApiUrl } from '@/lib/api';

// ==================== 类型定义 ====================

/**
 * 代币自动更新状态
 */
export interface SymbolUpdateStatus {
  symbol: string;
  autoUpdate: boolean;
  lastUpdate: string | null;
  isActive: boolean;
}

/**
 * 自动更新服务状态响应
 */
export interface AutoUpdateStatusResponse {
  symbols: SymbolUpdateStatus[];
  isRunning: boolean;
  lastCheckTime: string | null;
}

/**
 * 操作响应
 */
export interface UpdateOperationResponse {
  success: boolean;
  message: string;
  affected: string[];
  invalid?: string[];
}

// ==================== 服务函数 ====================

/**
 * 获取自动更新状态
 */
export async function getAutoUpdateStatus(): Promise<AutoUpdateStatusResponse> {
  try {
    const response = await fetch(buildApiUrl('/api/auto-update/status'));
    
    if (!response.ok) {
      throw new Error('Failed to fetch auto-update status');
    }
    
    const data = await response.json();
    
    return {
      symbols: data.symbols.map((s: any) => ({
        symbol: s.symbol,
        autoUpdate: s.auto_update,
        lastUpdate: s.last_update,
        isActive: s.is_active,
      })),
      isRunning: data.is_running ?? true,
      lastCheckTime: data.last_check_time ?? null,
    };
  } catch (error) {
    console.error('[AutoUpdateService] Failed to get status:', error);
    throw error;
  }
}

/**
 * 获取启用自动更新的代币列表
 */
export async function getEnabledSymbols(): Promise<string[]> {
  const status = await getAutoUpdateStatus();
  return status.symbols
    .filter(s => s.autoUpdate)
    .map(s => s.symbol);
}

/**
 * 启用指定代币的自动更新
 */
export async function enableAutoUpdate(symbols: string[]): Promise<UpdateOperationResponse> {
  try {
    const response = await fetch(buildApiUrl('/api/auto-update/enable'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to enable auto-update');
    }
    
    return {
      success: true,
      message: data.message || 'Auto-update enabled',
      affected: data.enabled || symbols,
      invalid: data.invalid,
    };
  } catch (error) {
    console.error('[AutoUpdateService] Failed to enable:', error);
    throw error;
  }
}

/**
 * 禁用指定代币的自动更新
 */
export async function disableAutoUpdate(symbols: string[]): Promise<UpdateOperationResponse> {
  try {
    const response = await fetch(buildApiUrl('/api/auto-update/disable'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to disable auto-update');
    }
    
    return {
      success: true,
      message: data.message || 'Auto-update disabled',
      affected: data.disabled || symbols,
    };
  } catch (error) {
    console.error('[AutoUpdateService] Failed to disable:', error);
    throw error;
  }
}

/**
 * 移除指定代币
 */
export async function removeSymbols(symbols: string[]): Promise<UpdateOperationResponse> {
  try {
    const response = await fetch(buildApiUrl('/api/auto-update/remove'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to remove symbols');
    }
    
    return {
      success: true,
      message: data.message || 'Symbols removed',
      affected: data.removed || symbols,
    };
  } catch (error) {
    console.error('[AutoUpdateService] Failed to remove:', error);
    throw error;
  }
}

/**
 * 手动触发指定代币的更新
 */
export async function triggerUpdate(symbols: string[]): Promise<UpdateOperationResponse> {
  try {
    const response = await fetch(buildApiUrl('/api/auto-update/trigger'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || 'Failed to trigger update');
    }
    
    return {
      success: true,
      message: data.message || 'Update triggered',
      affected: data.triggered || symbols,
    };
  } catch (error) {
    console.error('[AutoUpdateService] Failed to trigger:', error);
    throw error;
  }
}

/**
 * 添加新代币并启用自动更新
 */
export async function addSymbol(symbol: string): Promise<UpdateOperationResponse> {
  const normalizedSymbol = symbol.toUpperCase().replace('USDT', '');
  return enableAutoUpdate([normalizedSymbol]);
}

/**
 * 格式化最后更新时间为相对时间
 */
export function formatLastUpdateTime(isoString: string | null): string {
  if (!isoString) return '从未更新';
  
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins} 分钟前`;
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)} 小时前`;
  return `${Math.floor(diffMins / 1440)} 天前`;
}

/**
 * 检查代币是否需要更新（超过 10 分钟未更新）
 */
export function needsUpdate(lastUpdate: string | null): boolean {
  if (!lastUpdate) return true;
  
  const date = new Date(lastUpdate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  
  return diffMins >= 10;
}

// ==================== 导出 ====================

export const autoUpdateService = {
  getAutoUpdateStatus,
  getEnabledSymbols,
  enableAutoUpdate,
  disableAutoUpdate,
  removeSymbols,
  triggerUpdate,
  addSymbol,
  formatLastUpdateTime,
  needsUpdate,
};

export default autoUpdateService;
