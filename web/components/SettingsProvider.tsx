"use client"

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AppSettings, loadSettings, saveSettings, DEFAULT_SETTINGS } from '@/lib/settings';

interface SettingsContextType {
  settings: AppSettings;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
  isLoaded: boolean;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export function SettingsProvider({ children }: { children: ReactNode }) {
  // Initialize with default settings to avoid hydration mismatch
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    // Load settings on client side mount
    const stored = loadSettings();
    setSettings(stored);
    setIsLoaded(true);
  }, []);

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings(prev => {
      const updated = { ...prev, ...newSettings };
      saveSettings(updated);
      return updated;
    });
  };

  // Always render children to avoid layout shift and hydration issues.
  // Components can check isLoaded if they need to wait for real settings.
  return (
    <SettingsContext.Provider value={{ settings, updateSettings, isLoaded }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (context === undefined) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
}
