"use client";

/**
 * TabDataProvider - Tab 数据缓存 Provider
 * 
 * 用于在 Tab 切换时保持各 Tab 的数据状态，避免每次切换都重新加载。
 * 
 * ============ 无感化切换方案 ============
 * 
 * 方案 A（已采用）：使用 forceMount + CSS display 控制
 * - 在 page.tsx 中，所有 TabsContent 都使用 forceMount 属性
 * - 通过 style={{ display: activeTab === 'xxx' ? 'block' : 'none' }} 控制显示/隐藏
 * - 组件不会被卸载，数据保持在组件内部 state 中
 * - 优点：最简单有效，无需额外代码
 * - 缺点：所有 Tab 内容同时存在于 DOM 中（内存占用略高）
 * 
 * 方案 B（备选）：将数据提升到此 Provider
 * - 需要把各 Tab 的数据（如 MajorAssetModule 的价格数据）存入此 Provider
 * - 组件可以安全卸载，再次挂载时从 Provider 恢复数据
 * - 优点：DOM 更干净
 * - 缺点：需要大量代码改动，数据结构复杂
 * 
 * 当前此 Provider 主要用于保存用户的选择状态（如 range、filter 等），
 * 实际的数据缓存已通过方案 A（forceMount）实现。
 */

import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { NewsItem, StateScenarioResponse } from '@/lib/api';

// 缓存数据结构
interface CachedData<T> {
  data: T;
  timestamp: number;
  params?: string; // 用于判断参数是否变化
}

// 各 Tab 的数据类型
interface TabDataState {
  // News Tab
  newsRadar: CachedData<NewsItem[]> | null;
  newsRange: '24h' | '7d' | '14d' | '30d';
  newsSymbolFilter: string;
  
  // Scenario Tab
  scenarioData: CachedData<StateScenarioResponse> | null;
  scenarioPrimarySymbol: string;
  scenarioCompareData: CachedData<StateScenarioResponse[]> | null;
  
  // Market Overview Tab - 各币种数据独立缓存
  marketOverviewLoaded: boolean;
}

interface TabDataContextType {
  state: TabDataState;
  
  // News Tab
  setNewsRadar: (data: NewsItem[], range: '24h' | '7d' | '14d' | '30d') => void;
  getNewsRadar: (range: '24h' | '7d' | '14d' | '30d') => NewsItem[] | null;
  setNewsRange: (range: '24h' | '7d' | '14d' | '30d') => void;
  setNewsSymbolFilter: (symbol: string) => void;
  
  // Scenario Tab
  setScenarioData: (data: StateScenarioResponse, symbol: string) => void;
  getScenarioData: (symbol: string) => StateScenarioResponse | null;
  setScenarioPrimarySymbol: (symbol: string) => void;
  setScenarioCompareData: (data: StateScenarioResponse[]) => void;
  
  // Market Overview
  setMarketOverviewLoaded: (loaded: boolean) => void;
  
  // 通用
  clearCache: () => void;
  isCacheValid: (timestamp: number, maxAge?: number) => boolean;
}

const DEFAULT_CACHE_MAX_AGE = 5 * 60 * 1000; // 5 分钟

const TabDataContext = createContext<TabDataContextType | null>(null);

export function TabDataProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<TabDataState>({
    newsRadar: null,
    newsRange: '14d',
    newsSymbolFilter: 'ALL',
    scenarioData: null,
    scenarioPrimarySymbol: 'ZEC',
    scenarioCompareData: null,
    marketOverviewLoaded: false,
  });

  // 判断缓存是否有效
  const isCacheValid = useCallback((timestamp: number, maxAge = DEFAULT_CACHE_MAX_AGE) => {
    return Date.now() - timestamp < maxAge;
  }, []);

  // News Tab
  const setNewsRadar = useCallback((data: NewsItem[], range: '24h' | '7d' | '14d' | '30d') => {
    setState(prev => ({
      ...prev,
      newsRadar: { data, timestamp: Date.now(), params: range },
      newsRange: range,
    }));
  }, []);

  const getNewsRadar = useCallback((range: '24h' | '7d' | '14d' | '30d') => {
    if (!state.newsRadar) return null;
    // 检查参数是否匹配且缓存未过期
    if (state.newsRadar.params === range && isCacheValid(state.newsRadar.timestamp)) {
      return state.newsRadar.data;
    }
    return null;
  }, [state.newsRadar, isCacheValid]);

  const setNewsRange = useCallback((range: '24h' | '7d' | '14d' | '30d') => {
    setState(prev => ({ ...prev, newsRange: range }));
  }, []);

  const setNewsSymbolFilter = useCallback((symbol: string) => {
    setState(prev => ({ ...prev, newsSymbolFilter: symbol }));
  }, []);

  // Scenario Tab
  const setScenarioData = useCallback((data: StateScenarioResponse, symbol: string) => {
    setState(prev => ({
      ...prev,
      scenarioData: { data, timestamp: Date.now(), params: symbol },
      scenarioPrimarySymbol: symbol,
    }));
  }, []);

  const getScenarioData = useCallback((symbol: string) => {
    if (!state.scenarioData) return null;
    if (state.scenarioData.params === symbol && isCacheValid(state.scenarioData.timestamp)) {
      return state.scenarioData.data;
    }
    return null;
  }, [state.scenarioData, isCacheValid]);

  const setScenarioPrimarySymbol = useCallback((symbol: string) => {
    setState(prev => ({ ...prev, scenarioPrimarySymbol: symbol }));
  }, []);

  const setScenarioCompareData = useCallback((data: StateScenarioResponse[]) => {
    setState(prev => ({
      ...prev,
      scenarioCompareData: { data, timestamp: Date.now() },
    }));
  }, []);

  // Market Overview
  const setMarketOverviewLoaded = useCallback((loaded: boolean) => {
    setState(prev => ({ ...prev, marketOverviewLoaded: loaded }));
  }, []);

  // 清除所有缓存
  const clearCache = useCallback(() => {
    setState({
      newsRadar: null,
      newsRange: '14d',
      newsSymbolFilter: 'ALL',
      scenarioData: null,
      scenarioPrimarySymbol: 'ZEC',
      scenarioCompareData: null,
      marketOverviewLoaded: false,
    });
  }, []);

  const value: TabDataContextType = {
    state,
    setNewsRadar,
    getNewsRadar,
    setNewsRange,
    setNewsSymbolFilter,
    setScenarioData,
    getScenarioData,
    setScenarioPrimarySymbol,
    setScenarioCompareData,
    setMarketOverviewLoaded,
    clearCache,
    isCacheValid,
  };

  return (
    <TabDataContext.Provider value={value}>
      {children}
    </TabDataContext.Provider>
  );
}

export function useTabData() {
  const context = useContext(TabDataContext);
  if (!context) {
    throw new Error('useTabData must be used within a TabDataProvider');
  }
  return context;
}
