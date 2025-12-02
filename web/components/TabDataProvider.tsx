"use client";

/**
 * TabDataProvider - Tab 数据缓存 Provider
 * 
 * 统一管理所有 Tab 的数据缓存，实现无感化切换。
 * 
 * ============ 统一方案 ============
 * 
 * 所有 Tab 的数据都存储在此 Provider 中：
 * - Dashboard（代币看板）：价格、注意力、新闻、事件等
 * - News Radar（新闻雷达）：雷达图数据
 * - Scenario（情景分析）：情景数据
 * - Market Overview：市场概览状态
 * 
 * 结合 forceMount + CSS display 控制，实现：
 * 1. 组件不卸载，内部 state 保持
 * 2. 即使热重载，数据也在 Provider 中持久化
 * 3. 切换 Tab 时无需重新加载
 */

import React, { createContext, useContext, useState, useCallback } from 'react';
import { 
  NewsItem, 
  StateScenarioResponse, 
  PriceCandle, 
  AttentionData, 
  SummaryStats,
  AttentionEvent,
  Timeframe,
} from '@/lib/api';

// 轻量级新闻类型：用于 Radar 统计，减少内存占用
type CompactNewsItem = Pick<NewsItem, 'datetime' | 'source' | 'language' | 'symbols' | 'source_weight' | 'sentiment_score'>;

// 缓存数据结构
interface CachedData<T> {
  data: T;
  timestamp: number;
  params?: string; // 用于判断参数是否变化
}

// Dashboard 数据结构
interface DashboardData {
  priceData: PriceCandle[];
  overviewPriceData: PriceCandle[];
  attentionData: AttentionData[];
  newsData: NewsItem[];
  assetNewsData: NewsItem[];
  events: AttentionEvent[];
  summaryStats: SummaryStats | null;
  selectedSymbol: string;
  selectedTimeframe: Timeframe;
  lastUpdate: number;
}

// 各 Tab 的数据类型
interface TabDataState {
  // Dashboard Tab（代币看板）
  dashboard: DashboardData | null;
  
  // News Tab - 使用轻量级类型减少内存
  newsRadar: CachedData<CompactNewsItem[]> | null;
  newsRange: '24h' | '7d' | '14d' | '30d';
  newsSymbolFilter: string;
  
  // Scenario Tab
  scenarioData: CachedData<StateScenarioResponse> | null;
  scenarioPrimarySymbol: string;
  scenarioCompareData: CachedData<StateScenarioResponse[]> | null;
  
  // Market Overview Tab
  marketOverviewLoaded: boolean;
}

interface TabDataContextType {
  state: TabDataState;
  
  // Dashboard Tab
  setDashboardData: (data: Partial<DashboardData>) => void;
  getDashboardData: () => DashboardData | null;
  updateDashboardPartial: (updates: Partial<DashboardData>) => void;
  
  // News Tab
  setNewsRadar: (data: CompactNewsItem[], range: '24h' | '7d' | '14d' | '30d') => void;
  getNewsRadar: (range: '24h' | '7d' | '14d' | '30d') => CompactNewsItem[] | null;
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

// Dashboard 默认值
const DEFAULT_DASHBOARD: DashboardData = {
  priceData: [],
  overviewPriceData: [],
  attentionData: [],
  newsData: [],
  assetNewsData: [],
  events: [],
  summaryStats: null,
  selectedSymbol: 'ZEC',
  selectedTimeframe: '1D',
  lastUpdate: 0,
};

export function TabDataProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<TabDataState>({
    dashboard: null,
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

  // Dashboard Tab
  const setDashboardData = useCallback((data: Partial<DashboardData>) => {
    setState(prev => ({
      ...prev,
      dashboard: {
        ...DEFAULT_DASHBOARD,
        ...prev.dashboard,
        ...data,
        lastUpdate: Date.now(),
      },
    }));
  }, []);

  const getDashboardData = useCallback(() => {
    return state.dashboard;
  }, [state.dashboard]);

  const updateDashboardPartial = useCallback((updates: Partial<DashboardData>) => {
    setState(prev => {
      if (!prev.dashboard) return prev;
      return {
        ...prev,
        dashboard: {
          ...prev.dashboard,
          ...updates,
          lastUpdate: Date.now(),
        },
      };
    });
  }, []);

  // News Tab
  const setNewsRadar = useCallback((data: CompactNewsItem[], range: '24h' | '7d' | '14d' | '30d') => {
    setState(prev => ({
      ...prev,
      newsRadar: { data, timestamp: Date.now(), params: range },
      newsRange: range,
    }));
  }, []);

  const getNewsRadar = useCallback((range: '24h' | '7d' | '14d' | '30d') => {
    if (!state.newsRadar) return null;
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
      dashboard: null,
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
    setDashboardData,
    getDashboardData,
    updateDashboardPartial,
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
