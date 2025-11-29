export type AppSettings = {
  autoUpdatePrice: boolean;
  defaultAttentionSource: 'composite' | 'news_channel';
  defaultTimeframe: '1D' | '4H';
  defaultWindowDays: number;
};

const SETTINGS_KEY = 'crypto-attention-lab:app-settings';

const DEFAULT_SETTINGS: AppSettings = {
  autoUpdatePrice: true,
  defaultAttentionSource: 'composite',
  defaultTimeframe: '1D',
  defaultWindowDays: 30,
};

export function loadSettings(): AppSettings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS;
  
  try {
    const stored = localStorage.getItem(SETTINGS_KEY);
    if (!stored) return DEFAULT_SETTINGS;
    
    const parsed = JSON.parse(stored);
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch (e) {
    console.error('Failed to load settings:', e);
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(settings: AppSettings): void {
  if (typeof window === 'undefined') return;
  
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (e) {
    console.error('Failed to save settings:', e);
  }
}
