/**
 * ==========================================================================
 * Regime-Driven Strategy Preset Hooks
 * 用于研究注意力 Regime 驱动的策略，从 localStorage 持久化和管理策略预设
 * ==========================================================================
 */

import { useCallback, useEffect, useState } from 'react';
import type { AttentionCondition, StrategyPreset } from '@/lib/api';

const PRESET_KEY = 'regime-strategy-presets';

function generateId(): string {
  return `preset-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

export function useStrategyPresets() {
  const [presets, setPresets] = useState<StrategyPreset[]>([]);

  const loadPresets = useCallback((): StrategyPreset[] => {
    if (typeof window === 'undefined') return [];
    try {
      const raw = window.localStorage.getItem(PRESET_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw) as StrategyPreset[];
      if (!Array.isArray(parsed)) return [];
      return parsed;
    } catch {
      return [];
    }
  }, []);

  const persistPresets = useCallback((list: StrategyPreset[]) => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(PRESET_KEY, JSON.stringify(list));
    } catch (e) {
      console.error('Failed to persist presets', e);
    }
  }, []);

  useEffect(() => {
    const loaded = loadPresets();
    setPresets(loaded);
  }, [loadPresets]);

  const addPreset = useCallback(
    (name: string, condition: AttentionCondition): StrategyPreset => {
      const newPreset: StrategyPreset = {
        id: generateId(),
        name: name.trim() || 'Untitled',
        description: 'User created preset',
        attention_condition: condition,
        params: {
          lookback_days: condition.lookback_days || 30,
          attention_quantile: condition.lower_quantile || 0.8,
          holding_days: 3,
        }
      };
      setPresets(prev => {
        const updated = [...prev, newPreset];
        persistPresets(updated);
        return updated;
      });
      return newPreset;
    },
    [persistPresets]
  );

  const updatePreset = useCallback(
    (id: string, patch: Partial<Omit<StrategyPreset, 'id'>>) => {
      setPresets(prev => {
        const updated = prev.map(p => (p.id === id ? { ...p, ...patch } : p));
        persistPresets(updated);
        return updated;
      });
    },
    [persistPresets]
  );

  const deletePreset = useCallback(
    (id: string) => {
      setPresets(prev => {
        const updated = prev.filter(p => p.id !== id);
        persistPresets(updated);
        return updated;
      });
    },
    [persistPresets]
  );

  const getPresetById = useCallback(
    (id: string): StrategyPreset | undefined => {
      return presets.find(p => p.id === id);
    },
    [presets]
  );

  return {
    presets,
    addPreset,
    updatePreset,
    deletePreset,
    getPresetById,
  };
}

/** 将 AttentionCondition 格式化为简洁的可读摘要 */
export function formatConditionSummary(cond: AttentionCondition | null | undefined): string {
  if (!cond) return '—';
  const source = cond.source === 'composite' ? 'Composite' : 'News Channel';
  let regimeLabel: string = cond.regime || 'unknown';
  if (cond.regime === 'custom') {
    const l = cond.lower_quantile ?? 0;
    const u = cond.upper_quantile ?? 1;
    regimeLabel = `custom(${(l * 100).toFixed(0)}%-${(u * 100).toFixed(0)}%)`;
  }
  return `${source}, ${regimeLabel}, ${cond.lookback_days}d`;
}
