// 事件类型阈值设置
export type EventTypeThresholds = {
  attention_spike: number;       // 注意力尖峰阈值 (分位数 0.8-0.99)
  high_weighted_event: number;   // 高权重事件阈值
  high_bullish: number;          // 高看涨情绪阈值
  high_bearish: number;          // 高看跌情绪阈值
  event_intensity: boolean;      // 是否显示事件强度标志
};

// 事件类型启用/禁用设置
export type EventTypeVisibility = {
  attention_spike: boolean;
  high_weighted_event: boolean;
  high_bullish: boolean;
  high_bearish: boolean;
  event_intensity: boolean;
};

export type AppSettings = {
  autoUpdatePrice: boolean;
  defaultAttentionSource: 'composite' | 'news_channel';
  defaultTimeframe: '1D' | '4H';
  defaultWindowDays: number;
  // Event detection settings
  showEventMarkers: boolean;
  eventDetectionQuantile: number;        // 兼容旧设置：全局分位数（用于 API 请求）
  eventDetectionLookbackDays: number;    // 事件检测回溯天数
  eventTypeThresholds: EventTypeThresholds;  // 每种事件类型的阈值
  eventTypeVisibility: EventTypeVisibility;  // 每种事件类型的显示开关
};

const SETTINGS_KEY = 'crypto-attention-lab:app-settings';

export const DEFAULT_EVENT_THRESHOLDS: EventTypeThresholds = {
  attention_spike: 0.9,         // 默认 Top 10%
  high_weighted_event: 0.85,    // 默认 Top 15%
  high_bullish: 0.85,
  high_bearish: 0.85,
  event_intensity: true,
};

export const DEFAULT_EVENT_VISIBILITY: EventTypeVisibility = {
  attention_spike: true,
  high_weighted_event: true,
  high_bullish: true,
  high_bearish: true,
  event_intensity: true,
};

export const DEFAULT_SETTINGS: AppSettings = {
  autoUpdatePrice: true,
  defaultAttentionSource: 'composite',
  defaultTimeframe: '1D',
  defaultWindowDays: 30,
  showEventMarkers: true,
  eventDetectionQuantile: 0.9,
  eventDetectionLookbackDays: 30,
  eventTypeThresholds: DEFAULT_EVENT_THRESHOLDS,
  eventTypeVisibility: DEFAULT_EVENT_VISIBILITY,
};

export function loadSettings(): AppSettings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS;
  
  try {
    const stored = localStorage.getItem(SETTINGS_KEY);
    if (!stored) return DEFAULT_SETTINGS;
    
    const parsed = JSON.parse(stored);
    // 深度合并嵌套对象，确保新增的字段有默认值
    return {
      ...DEFAULT_SETTINGS,
      ...parsed,
      eventTypeThresholds: {
        ...DEFAULT_EVENT_THRESHOLDS,
        ...(parsed.eventTypeThresholds || {}),
      },
      eventTypeVisibility: {
        ...DEFAULT_EVENT_VISIBILITY,
        ...(parsed.eventTypeVisibility || {}),
      },
    };
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
