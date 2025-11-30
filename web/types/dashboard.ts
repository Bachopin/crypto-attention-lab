import { 
  Candle, 
  AttentionPoint, 
  NewsItem, 
  AttentionEvent, 
  SummaryStats, 
  Timeframe 
} from './models';

export interface DashboardData {
  summary: SummaryStats | null;
  price: Candle[];
  attention: AttentionPoint[];
  news: NewsItem[];
  events: AttentionEvent[];
  overview: Candle[];
}

export interface DashboardState {
  data: DashboardData;
  loading: boolean;
  updating: boolean;
  error: string | null;
}
