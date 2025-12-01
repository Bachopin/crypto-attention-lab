/**
 * 服务层统一导出
 */

// Dashboard 聚合服务（已存在）
export { dashboardService, DashboardService } from './dashboard-service';

// 价格服务
export { priceService, default as PriceService } from './price-service';

// 注意力服务
export { attentionService, default as AttentionService } from './attention-service';

// 回测服务
export { backtestService, default as BacktestService } from './backtest-service';

// 自动更新服务
export { autoUpdateService, default as AutoUpdateService } from './auto-update-service';

// 情景分析服务
export { scenarioService } from './scenario-service';

// 新闻服务
export { newsService } from './news-service';

// 类型导出
export type { SymbolUpdateStatus, AutoUpdateStatusResponse, UpdateOperationResponse } from './auto-update-service';
export type { ScenarioSearchParams, ScenarioAnalysisResult } from './scenario-service';
export type { NewsSearchParams, NewsTrendParams } from './news-service';
