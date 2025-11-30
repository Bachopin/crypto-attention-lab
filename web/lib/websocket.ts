/**
 * WebSocket 实时数据服务
 * 提供价格和注意力数据的实时订阅
 * 
 * 设计原则：
 * - WebSocket 是可选的增强功能，连接失败不影响应用正常使用
 * - 自动重连机制，指数退避
 * - 与 REST API 配合使用：WebSocket 提供实时更新，REST API 提供历史数据
 * 
 * 使用说明：
 * - useRealtimePrice: 订阅单个代币的实时价格
 * - useRealtimePrices: 订阅多个代币的实时价格
 * - useRealtimeAttention: 订阅注意力数据和事件
 * - useWebSocketStatus: 监控连接状态
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { buildApiUrl } from '@/lib/api';

// WebSocket 服务端地址
// 在 Codespaces/代理环境中，WebSocket 需要直接连接到后端
// 开发环境：ws://localhost:8000
// 生产环境：通过 NEXT_PUBLIC_WS_URL 配置
function getWebSocketBaseUrl(): string {
  // 优先使用环境变量
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }
  
  // 客户端：检测是否在本地开发环境
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    
    // 本地开发环境直接连接 8000 端口
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return `ws://${hostname}:8000`;
    }
    
    // Codespaces / Cloud IDE 环境适配
    // 典型格式: name-3000.app.github.dev -> name-8000.app.github.dev
    if (hostname.includes('github.dev') || hostname.includes('gitpod.io')) {
      // 尝试替换 URL 中的端口标识
      if (hostname.includes('-3000')) {
        return `${protocol}//${hostname.replace('-3000', '-8000')}`;
      }
    }
    
    // 其他环境：尝试使用相同主机但 8000 端口
    // 注意：如果是在 Codespaces 但没有 -3000 后缀，这可能会失败
    return `${protocol}//${hostname}:8000`;
  }
  
  // 服务端渲染默认值
  return 'ws://localhost:8000';
}

const WS_BASE_URL = getWebSocketBaseUrl();

// 配置
const WS_CONFIG = {
  maxReconnectAttempts: 10,
  initialReconnectDelay: 1000,
  maxReconnectDelay: 30000,
  pingInterval: 30000,
  connectionTimeout: 5000,
};

// ==================== Types ====================

export interface RealtimePriceData {
  timestamp: number;
  datetime: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  is_closed: boolean;
}

export interface RealtimeAttentionData {
  timestamp: number;
  datetime: string;
  attention_score: number;
  news_count: number;
  composite_attention_score?: number;
}

export interface AttentionEventData {
  event_type: string;
  intensity: number;
  summary: string;
  timestamp: string;
}

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'unavailable';

export interface WebSocketMessage {
  type: string;
  symbol?: string;
  data?: any;
  event?: any;
  message?: string;
  symbols?: string[];
}

// ==================== WebSocket Manager ====================

class WebSocketManager {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = WS_CONFIG.maxReconnectAttempts;
  private reconnectDelay = WS_CONFIG.initialReconnectDelay;
  private pingInterval: NodeJS.Timeout | null = null;
  private connectionTimeout: NodeJS.Timeout | null = null;
  private listeners: Map<string, Set<(data: WebSocketMessage) => void>> = new Map();
  private statusListeners: Set<(status: WebSocketStatus) => void> = new Set();
  private subscribedSymbols: Set<string> = new Set();
  private _status: WebSocketStatus = 'disconnected';
  private _isManualDisconnect = false;

  constructor(endpoint: string) {
    this.url = `${WS_BASE_URL}${endpoint}`;
  }

  get status(): WebSocketStatus {
    return this._status;
  }
  
  get isConnected(): boolean {
    return this._status === 'connected';
  }

  private setStatus(status: WebSocketStatus) {
    this._status = status;
    this.statusListeners.forEach(listener => listener(status));
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.setStatus('connecting');
    
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WebSocket] Connected to', this.url);
        this.setStatus('connected');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;

        // 重新订阅之前的 symbols
        if (this.subscribedSymbols.size > 0) {
          this.send({
            action: 'subscribe',
            symbols: Array.from(this.subscribedSymbols)
          });
        }

        // 启动心跳
        this.startPing();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (e) {
          console.error('[WebSocket] Failed to parse message:', e);
        }
      };

      this.ws.onclose = (event) => {
        console.log('[WebSocket] Disconnected:', event.code, event.reason);
        this.setStatus('disconnected');
        this.stopPing();
        this.attemptReconnect();
      };

      this.ws.onerror = (event) => {
        // WebSocket error events usually don't contain detailed error messages for security reasons
        console.warn(`[WebSocket] Connection error to ${this.url}. Retrying...`);
        this.setStatus('error');
      };
    } catch (e) {
      console.error('[WebSocket] Connection failed:', e);
      this.setStatus('error');
      this.attemptReconnect();
    }
  }

  disconnect(): void {
    this.stopPing();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(`[WebSocket] Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect();
    }, this.reconnectDelay);

    // 指数退避
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, 30000);
  }

  private startPing(): void {
    this.stopPing();
    this.pingInterval = setInterval(() => {
      this.send({ action: 'ping' });
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  send(data: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  subscribe(symbols: string[]): void {
    symbols.forEach(s => this.subscribedSymbols.add(s.toUpperCase()));
    
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({
        action: 'subscribe',
        symbols: symbols.map(s => s.toUpperCase())
      });
    }
  }

  unsubscribe(symbols: string[]): void {
    symbols.forEach(s => this.subscribedSymbols.delete(s.toUpperCase()));
    
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.send({
        action: 'unsubscribe',
        symbols: symbols.map(s => s.toUpperCase())
      });
    }
  }

  private handleMessage(message: WebSocketMessage): void {
    const { type } = message;

    // 调用对应类型的监听器
    const typeListeners = this.listeners.get(type);
    if (typeListeners) {
      typeListeners.forEach(listener => listener(message));
    }

    // 调用通用监听器
    const allListeners = this.listeners.get('*');
    if (allListeners) {
      allListeners.forEach(listener => listener(message));
    }
  }

  on(type: string, callback: (data: WebSocketMessage) => void): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(callback);

    // 返回取消订阅函数
    return () => {
      this.listeners.get(type)?.delete(callback);
    };
  }

  onStatusChange(callback: (status: WebSocketStatus) => void): () => void {
    this.statusListeners.add(callback);
    return () => {
      this.statusListeners.delete(callback);
    };
  }

  getSubscribedSymbols(): string[] {
    return Array.from(this.subscribedSymbols);
  }
}

// ==================== Singleton Instances ====================

let priceWsManager: WebSocketManager | null = null;
let attentionWsManager: WebSocketManager | null = null;

export function getPriceWebSocket(): WebSocketManager {
  if (!priceWsManager) {
    priceWsManager = new WebSocketManager('/ws/price');
  }
  return priceWsManager;
}

export function getAttentionWebSocket(): WebSocketManager {
  if (!attentionWsManager) {
    attentionWsManager = new WebSocketManager('/ws/attention');
  }
  return attentionWsManager;
}

// ==================== React Hooks ====================

/**
 * 实时价格数据 Hook
 * 
 * @param symbol 交易对符号，如 "BTC"
 * @param enabled 是否启用 WebSocket 连接
 * @param fallbackToRest 连接失败时是否回退到 REST API 轮询（默认 true）
 * @returns { data, status, lastUpdate, isRealtime }
 * 
 * @example
 * ```tsx
 * const { data, status, isRealtime } = useRealtimePrice('BTC');
 * 
 * if (data) {
 *   console.log(`Current price: ${data.close}, realtime: ${isRealtime}`);
 * }
 * ```
 */
export function useRealtimePrice(symbol: string, enabled = true, fallbackToRest = true) {
  const [data, setData] = useState<RealtimePriceData | null>(null);
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [isRealtime, setIsRealtime] = useState(false);
  const wsRef = useRef<WebSocketManager | null>(null);
  const fallbackIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 清理回退轮询
  const clearFallback = useCallback(() => {
    if (fallbackIntervalRef.current) {
      clearInterval(fallbackIntervalRef.current);
      fallbackIntervalRef.current = null;
    }
  }, []);

  // REST API 回退轮询
  const startFallbackPolling = useCallback(async () => {
    if (!fallbackToRest || !symbol) return;
    
    const fetchPrice = async () => {
      try {
        const response = await fetch(
          buildApiUrl(`/api/price?symbol=${symbol}USDT&timeframe=15m&limit=1`)
        );
        if (response.ok) {
          const prices = await response.json();
          if (prices && prices.length > 0) {
            const latest = prices[prices.length - 1];
            setData({
              timestamp: latest.timestamp,
              datetime: latest.datetime,
              open: latest.open,
              high: latest.high,
              low: latest.low,
              close: latest.close,
              volume: latest.volume,
              is_closed: true,
            });
            setLastUpdate(new Date());
            setIsRealtime(false);
          }
        }
      } catch (e) {
        console.warn('[WebSocket Fallback] REST API fetch failed:', e);
      }
    };

    // 立即获取一次
    await fetchPrice();
    
    // 每 30 秒轮询
    fallbackIntervalRef.current = setInterval(fetchPrice, 30000);
  }, [symbol, fallbackToRest]);

  useEffect(() => {
    if (!enabled || !symbol) return;

    const ws = getPriceWebSocket();
    wsRef.current = ws;

    // 连接 WebSocket
    ws.connect();

    // 订阅状态变化
    const unsubStatus = ws.onStatusChange((newStatus) => {
      setStatus(newStatus);
      
      // WebSocket 连接成功，停止回退轮询
      if (newStatus === 'connected') {
        clearFallback();
        setIsRealtime(true);
      }
      // WebSocket 断开或错误，启动回退轮询
      else if ((newStatus === 'error' || newStatus === 'disconnected') && fallbackToRest) {
        // 延迟启动回退，给 WebSocket 重连机会
        setTimeout(() => {
          if (wsRef.current?.status !== 'connected') {
            startFallbackPolling();
          }
        }, 5000);
      }
    });

    // 订阅价格更新
    const unsubPrice = ws.on('price_update', (message) => {
      if (message.symbol?.toUpperCase() === symbol.toUpperCase() && message.data) {
        setData(message.data as RealtimePriceData);
        setLastUpdate(new Date());
        setIsRealtime(true);
        // 收到 WebSocket 数据，停止回退轮询
        clearFallback();
      }
    });

    // 订阅 symbol
    ws.subscribe([symbol]);

    return () => {
      unsubStatus();
      unsubPrice();
      ws.unsubscribe([symbol]);
      clearFallback();
    };
  }, [symbol, enabled, fallbackToRest, clearFallback, startFallbackPolling]);

  return { data, status, lastUpdate, isRealtime };
}

/**
 * 多个交易对的实时价格 Hook
 * 
 * @param symbols 交易对数组
 * @param enabled 是否启用
 * @returns { prices, status }
 */
export function useRealtimePrices(symbols: string[], enabled = true) {
  const [prices, setPrices] = useState<Record<string, RealtimePriceData>>({});
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const wsRef = useRef<WebSocketManager | null>(null);
  
  // 使用 useMemo 来稳定 symbols 依赖
  const symbolsKey = symbols.join(',');

  useEffect(() => {
    if (!enabled || symbols.length === 0) return;

    const ws = getPriceWebSocket();
    wsRef.current = ws;

    ws.connect();

    const unsubStatus = ws.onStatusChange(setStatus);

    const unsubPrice = ws.on('price_update', (message) => {
      if (message.symbol && message.data) {
        setPrices(prev => ({
          ...prev,
          [message.symbol!.toUpperCase()]: message.data as RealtimePriceData
        }));
      }
    });

    ws.subscribe(symbols);

    return () => {
      unsubStatus();
      unsubPrice();
      ws.unsubscribe(symbols);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey, enabled]);

  return { prices, status };
}

/**
 * 实时注意力数据 Hook
 * 
 * @param symbol 代币符号
 * @param enabled 是否启用
 */
export function useRealtimeAttention(symbol: string, enabled = true) {
  const [data, setData] = useState<RealtimeAttentionData | null>(null);
  const [events, setEvents] = useState<AttentionEventData[]>([]);
  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const wsRef = useRef<WebSocketManager | null>(null);

  useEffect(() => {
    if (!enabled || !symbol) return;

    const ws = getAttentionWebSocket();
    wsRef.current = ws;

    ws.connect();

    const unsubStatus = ws.onStatusChange(setStatus);

    const unsubAttention = ws.on('attention_update', (message) => {
      if (message.symbol?.toUpperCase() === symbol.toUpperCase() && message.data) {
        setData(message.data as RealtimeAttentionData);
      }
    });

    const unsubEvent = ws.on('attention_event', (message) => {
      if (message.symbol?.toUpperCase() === symbol.toUpperCase() && message.event) {
        setEvents(prev => [message.event as AttentionEventData, ...prev].slice(0, 50));
      }
    });

    ws.subscribe([symbol]);

    return () => {
      unsubStatus();
      unsubAttention();
      unsubEvent();
      ws.unsubscribe([symbol]);
    };
  }, [symbol, enabled]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { data, events, status, clearEvents };
}

/**
 * WebSocket 连接状态指示器 Hook
 */
export function useWebSocketStatus() {
  const [priceStatus, setPriceStatus] = useState<WebSocketStatus>('disconnected');
  const [attentionStatus, setAttentionStatus] = useState<WebSocketStatus>('disconnected');

  useEffect(() => {
    const priceWs = getPriceWebSocket();
    const attentionWs = getAttentionWebSocket();

    const unsubPrice = priceWs.onStatusChange(setPriceStatus);
    const unsubAttention = attentionWs.onStatusChange(setAttentionStatus);

    // 获取当前状态
    setPriceStatus(priceWs.status);
    setAttentionStatus(attentionWs.status);

    return () => {
      unsubPrice();
      unsubAttention();
    };
  }, []);

  return { priceStatus, attentionStatus };
}

/**
 * 手动控制 WebSocket 连接的 Hook
 */
export function useWebSocketControl() {
  const connectPrice = useCallback(() => {
    getPriceWebSocket().connect();
  }, []);

  const disconnectPrice = useCallback(() => {
    getPriceWebSocket().disconnect();
  }, []);

  const connectAttention = useCallback(() => {
    getAttentionWebSocket().connect();
  }, []);

  const disconnectAttention = useCallback(() => {
    getAttentionWebSocket().disconnect();
  }, []);

  const connectAll = useCallback(() => {
    connectPrice();
    connectAttention();
  }, [connectPrice, connectAttention]);

  const disconnectAll = useCallback(() => {
    disconnectPrice();
    disconnectAttention();
  }, [disconnectPrice, disconnectAttention]);

  return {
    connectPrice,
    disconnectPrice,
    connectAttention,
    disconnectAttention,
    connectAll,
    disconnectAll,
  };
}
