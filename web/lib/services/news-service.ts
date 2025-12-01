/**
 * News Service
 * 
 * 新闻数据服务层 - 封装新闻获取与处理逻辑
 */

import { fetchNews, fetchNewsCount, fetchNewsTrend } from '@/lib/api';
import type { NewsItem, NewsTrendPoint } from '@/types/models';

// ============================================================
// Service Types
// ============================================================

export interface NewsSearchParams {
  symbol?: string;
  source?: string;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
}

export interface NewsTrendParams {
  symbol?: string;
  interval?: '1h' | '1d';
  start?: string;
  end?: string;
}

export interface NewsStats {
  total: number;
  todayCount: number;
  weekCount: number;
  avgPerDay: number;
  topSources: Array<{ source: string; count: number }>;
}

// ============================================================
// Service Implementation
// ============================================================

class NewsService {
  /**
   * 获取新闻列表
   */
  async getNews(params: NewsSearchParams = {}): Promise<NewsItem[]> {
    const { symbol, source, start, end, limit = 50 } = params;
    
    return fetchNews({
      symbol,
      source,
      start,
      end,
      limit,
    });
  }

  /**
   * 获取最新新闻（默认最近 10 条）
   */
  async getLatestNews(symbol?: string, count: number = 10): Promise<NewsItem[]> {
    return this.getNews({ symbol, limit: count });
  }

  /**
   * 获取新闻数量
   */
  async getNewsCount(params: NewsSearchParams = {}): Promise<number> {
    const result = await fetchNewsCount({
      symbol: params.symbol,
      source: params.source,
      start: params.start,
      end: params.end,
    });
    return result.total;
  }

  /**
   * 获取新闻趋势
   */
  async getNewsTrend(params: NewsTrendParams = {}): Promise<NewsTrendPoint[]> {
    const {
      symbol,
      interval = '1d',
      start,
      end,
    } = params;

    return fetchNewsTrend({
      symbol,
      interval,
      start,
      end,
    });
  }

  /**
   * 获取今日新闻
   */
  async getTodayNews(symbol?: string): Promise<NewsItem[]> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    return this.getNews({
      symbol,
      start: today.toISOString(),
    });
  }

  /**
   * 按来源分组新闻
   */
  async getNewsBySource(symbol?: string): Promise<Map<string, NewsItem[]>> {
    const news = await this.getNews({ symbol, limit: 100 });
    
    const grouped = new Map<string, NewsItem[]>();
    news.forEach((item) => {
      const source = item.source || 'Unknown';
      if (!grouped.has(source)) {
        grouped.set(source, []);
      }
      grouped.get(source)!.push(item);
    });
    
    return grouped;
  }

  /**
   * 搜索新闻（按标题关键词）
   */
  filterByKeyword(news: NewsItem[], keyword: string): NewsItem[] {
    const lowerKeyword = keyword.toLowerCase();
    return news.filter((item) =>
      item.title.toLowerCase().includes(lowerKeyword)
    );
  }

  /**
   * 按情绪分数排序新闻
   */
  sortBySentiment(news: NewsItem[], ascending: boolean = false): NewsItem[] {
    return [...news].sort((a, b) => {
      const scoreA = a.sentiment_score ?? 0;
      const scoreB = b.sentiment_score ?? 0;
      return ascending ? scoreA - scoreB : scoreB - scoreA;
    });
  }

  /**
   * 格式化新闻日期显示
   */
  formatNewsDate(datetime: string): string {
    const date = new Date(datetime);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffHours < 1) {
      const diffMinutes = Math.floor(diffMs / (1000 * 60));
      return `${diffMinutes} 分钟前`;
    }
    if (diffHours < 24) {
      return `${diffHours} 小时前`;
    }
    if (diffDays < 7) {
      return `${diffDays} 天前`;
    }
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
    });
  }

  /**
   * 获取情绪标签
   */
  getSentimentLabel(score: number | undefined): {
    label: string;
    color: string;
  } {
    if (score === undefined || score === null) {
      return { label: '中性', color: 'text-gray-500' };
    }
    if (score > 0.3) {
      return { label: '正面', color: 'text-green-500' };
    }
    if (score < -0.3) {
      return { label: '负面', color: 'text-red-500' };
    }
    return { label: '中性', color: 'text-gray-500' };
  }
}

// ============================================================
// Export singleton instance
// ============================================================

export const newsService = new NewsService();
