"use client"

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { AppSettings, loadSettings, saveSettings } from '@/lib/settings';

interface SettingsContextType {
  settings: AppSettings;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
}

const SettingsContext = createContext<SettingsContextType | undefined>(undefined);

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(loadSettings());
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // Load settings on client side mount
    setSettings(loadSettings());
    setLoaded(true);
  }, []);

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings(prev => {
      const updated = { ...prev, ...newSettings };
      saveSettings(updated);
      return updated;
    });
  };

  if (!loaded) {
    // Prevent rendering children until settings are loaded to ensure
    // consistent state and avoid hydration mismatches.
    return null; 
  }

  return (
    <SettingsContext.Provider value={{ settings, updateSettings }}>
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
