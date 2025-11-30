import {
  fetchPrice,
  fetchAttention,
  fetchNews,
  fetchAttentionEvents,
  fetchSummaryStats,
  Timeframe,
  Candle,
  AttentionPoint,
  NewsItem,
  AttentionEvent,
  SummaryStats
} from '@/lib/api';
import { DashboardData } from '@/types/dashboard';

/**
 * Service to handle data fetching and transformation for the Dashboard.
 * Implements progressive loading strategy.
 */
export class DashboardService {
  
  /**
   * Fetches critical data required for the initial paint (Price Chart + Summary).
   */
  async fetchCriticalData(symbol: string, timeframe: Timeframe): Promise<{ summary: SummaryStats | null; price: Candle[] }> {
    try {
      // Limit initial price load to recent 300 candles to speed up TTI
      const [summary, price] = await Promise.all([
        fetchSummaryStats(symbol).catch(e => { 
          console.warn('[DashboardService] Stats fetch failed', e); 
          return null; 
        }),
        fetchPrice({ symbol: `${symbol}USDT`, timeframe, limit: 300 }).catch(e => { 
          throw e; 
        })
      ]);

      if (!price || price.length === 0) {
        throw new Error(`No price data available for ${symbol}`);
      }

      return { summary, price };
    } catch (error) {
      console.error('[DashboardService] Failed to fetch critical data', error);
      throw error;
    }
  }

  /**
   * Fetches secondary data (Attention, News, Events) that can be loaded after the main chart.
   */
  async fetchSecondaryData(symbol: string, startDate?: string): Promise<{ attention: AttentionPoint[]; news: NewsItem[]; events: AttentionEvent[] }> {
    try {
      const [attention, news, events] = await Promise.all([
        fetchAttention({ symbol, granularity: '1d', start: startDate }).catch(e => { 
          console.warn('[DashboardService] Attention fetch failed', e); 
          return []; 
        }),
        fetchNews({ symbol, limit: 20 }).catch(e => { 
          console.warn('[DashboardService] News fetch failed', e); 
          return []; 
        }),
        fetchAttentionEvents({ symbol, start: startDate }).catch(e => { 
          console.warn('[DashboardService] Events fetch failed', e); 
          return []; 
        }),
      ]);

      return { attention, news, events };
    } catch (error) {
      console.error('[DashboardService] Failed to fetch secondary data', error);
      return { attention: [], news: [], events: [] };
    }
  }

  /**
   * Fetches background data (Overview chart) that is not immediately visible.
   */
  async fetchBackgroundData(symbol: string): Promise<Candle[]> {
    try {
      // Use 1D instead of 4H for overview to reduce data size
      return await fetchPrice({ symbol: `${symbol}USDT`, timeframe: '1D', limit: 1000 });
    } catch (error) {
      console.warn('[DashboardService] Overview price fetch failed', error);
      return [];
    }
  }
}

export const dashboardService = new DashboardService();
