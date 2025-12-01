'use client';

import { useEffect } from 'react';

export default function StorageCleaner() {
  useEffect(() => {
    // 清理可能损坏的 localStorage
    if (typeof window !== 'undefined') {
      try {
        const test = '__storage_test__';
        localStorage.setItem(test, test);
        localStorage.removeItem(test);
      } catch (e) {
        console.warn('[Storage] localStorage appears corrupted, clearing...');
        try {
          localStorage.clear();
        } catch (clearError) {
          console.error('[Storage] Could not clear localStorage:', clearError);
        }
      }
    }
  }, []);

  return null;
}
