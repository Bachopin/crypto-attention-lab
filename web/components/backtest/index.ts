/**
 * 回测模块统一导出
 */

// 主组件
export { BacktestPanel } from './BacktestPanel';
export { default as BacktestPanelLegacy } from './BacktestPanelLegacy';

// 子组件
export { StatCard, StatGrid } from './StatCard';
export { EquityCurve, MultiEquityCurve } from './EquityCurve';
export { TradeTable } from './TradeTable';
export { StrategyOverview } from './StrategyOverview';
export { BacktestParamsForm } from './BacktestParamsForm';

// Hooks
export { useStrategyPresets } from './useStrategyPresets';

// 类型
export * from './types';
