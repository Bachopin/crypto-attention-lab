/**
 * 策略预设管理 Hook
 * 
 * 使用 localStorage 持久化存储策略配置和回测结果
 */

import { useState, useEffect, useCallback } from 'react';
import type { BacktestSummary, EquityPoint } from '@/types/models/backtest';
import type { AttentionCondition } from '@/types/models/attention';
import type { BacktestPanelParams, LocalStrategyPreset } from './types';

const STORAGE_PREFIX = 'backtest-preset-v2-';
const SUMMARY_PREFIX = 'backtest-summary-v2-';
const EQUITY_PREFIX = 'backtest-equity-v2-';

interface UseStrategyPresetsReturn {
  /** 所有预设名称 */
  presetNames: string[];
  /** 预设摘要数据 */
  summaries: Record<string, BacktestSummary>;
  /** 预设权益曲线数据 */
  equities: Record<string, EquityPoint[]>;
  /** 保存预设 */
  savePreset: (name: string, params: BacktestPanelParams, attentionCondition?: AttentionCondition | null) => void;
  /** 加载预设 */
  loadPreset: (name: string) => BacktestPanelParams | null;
  /** 删除预设 */
  deletePreset: (name: string) => void;
  /** 保存回测结果 */
  saveBacktestResult: (name: string, summary: BacktestSummary, equityCurve: EquityPoint[]) => void;
  /** 刷新预设列表 */
  refresh: () => void;
}

export function useStrategyPresets(): UseStrategyPresetsReturn {
  const [presetNames, setPresetNames] = useState<string[]>([]);
  const [summaries, setSummaries] = useState<Record<string, BacktestSummary>>({});
  const [equities, setEquities] = useState<Record<string, EquityPoint[]>>({});

  const loadAllPresets = useCallback(() => {
    if (typeof window === 'undefined') return;

    try {
      const names: string[] = [];
      const loadedSummaries: Record<string, BacktestSummary> = {};
      const loadedEquities: Record<string, EquityPoint[]> = {};

      for (let i = 0; i < window.localStorage.length; i++) {
        const key = window.localStorage.key(i);
        if (key && key.startsWith(STORAGE_PREFIX)) {
          const name = key.replace(STORAGE_PREFIX, '');
          names.push(name);

          // 加载摘要
          const summaryRaw = window.localStorage.getItem(`${SUMMARY_PREFIX}${name}`);
          if (summaryRaw) {
            try {
              loadedSummaries[name] = JSON.parse(summaryRaw);
            } catch {
              // 忽略解析错误
            }
          }

          // 加载权益曲线
          const equityRaw = window.localStorage.getItem(`${EQUITY_PREFIX}${name}`);
          if (equityRaw) {
            try {
              loadedEquities[name] = JSON.parse(equityRaw);
            } catch {
              // 忽略解析错误
            }
          }
        }
      }

      names.sort();
      setPresetNames(names);
      setSummaries(loadedSummaries);
      setEquities(loadedEquities);
    } catch (e) {
      console.error('Failed to load presets:', e);
    }
  }, []);

  useEffect(() => {
    loadAllPresets();
  }, [loadAllPresets]);

  const savePreset = useCallback((
    name: string,
    params: BacktestPanelParams,
    attentionCondition?: AttentionCondition | null
  ) => {
    if (typeof window === 'undefined') return;

    const trimmedName = name.trim() || 'default';
    try {
      const preset: LocalStrategyPreset = {
        id: trimmedName,
        name: trimmedName,
        params,
        attentionCondition,
        createdAt: new Date().toISOString(),
      };
      window.localStorage.setItem(`${STORAGE_PREFIX}${trimmedName}`, JSON.stringify(preset));
      loadAllPresets();
    } catch (e) {
      console.error('Failed to save preset:', e);
    }
  }, [loadAllPresets]);

  const loadPreset = useCallback((name: string): BacktestPanelParams | null => {
    if (typeof window === 'undefined') return null;

    try {
      const raw = window.localStorage.getItem(`${STORAGE_PREFIX}${name}`);
      if (!raw) return null;

      const preset: LocalStrategyPreset = JSON.parse(raw);
      return preset.params;
    } catch (e) {
      console.error('Failed to load preset:', e);
      return null;
    }
  }, []);

  const deletePreset = useCallback((name: string) => {
    if (typeof window === 'undefined') return;

    try {
      window.localStorage.removeItem(`${STORAGE_PREFIX}${name}`);
      window.localStorage.removeItem(`${SUMMARY_PREFIX}${name}`);
      window.localStorage.removeItem(`${EQUITY_PREFIX}${name}`);
      loadAllPresets();
    } catch (e) {
      console.error('Failed to delete preset:', e);
    }
  }, [loadAllPresets]);

  const saveBacktestResult = useCallback((
    name: string,
    summary: BacktestSummary,
    equityCurve: EquityPoint[]
  ) => {
    if (typeof window === 'undefined') return;

    try {
      window.localStorage.setItem(`${SUMMARY_PREFIX}${name}`, JSON.stringify(summary));
      window.localStorage.setItem(`${EQUITY_PREFIX}${name}`, JSON.stringify(equityCurve));
      
      // 更新本地状态
      setSummaries(prev => ({ ...prev, [name]: summary }));
      setEquities(prev => ({ ...prev, [name]: equityCurve }));
    } catch (e) {
      console.error('Failed to save backtest result:', e);
    }
  }, []);

  return {
    presetNames,
    summaries,
    equities,
    savePreset,
    loadPreset,
    deletePreset,
    saveBacktestResult,
    refresh: loadAllPresets,
  };
}

export default useStrategyPresets;
