# 前端架构重构指南

## 一、架构概览

### 重构后的分层架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              视图层 (Views)                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ web/app/*                    - 页面路由                                      ││
│  │ web/components/*             - 展示组件（接收 props，渲染 UI）               ││
│  │ web/components/containers/*  - 容器组件（连接服务层，管理状态）              ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          Hooks 层 (Custom Hooks)                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ web/lib/hooks/useAsync.ts    - 通用异步数据获取                              ││
│  │ web/lib/hooks/index.ts       - 统一导出                                      ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           服务层 (Services)                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ web/lib/services/                                                           ││
│  │   price-service.ts          - 价格数据获取与转换                             ││
│  │   attention-service.ts      - 注意力/事件/regime 数据                        ││
│  │   backtest-service.ts       - 回测执行与结果处理                             ││
│  │   auto-update-service.ts    - 自动更新状态管理                               ││
│  │   dashboard-service.ts      - Dashboard 聚合服务                             ││
│  │   index.ts                  - 统一导出                                       ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API 层 (API Client)                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ web/lib/api.ts              - HTTP 客户端、缓存、API 函数                    ││
│  │ web/lib/websocket.ts        - WebSocket 管理与 Hooks                         ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              类型层 (Types)                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ web/types/models/           - 领域模型类型                                   ││
│  │   common.ts                 - 通用类型（Timeframe, DateRange...）            ││
│  │   price.ts                  - 价格相关（PricePoint, PriceSeries...）         ││
│  │   attention.ts              - 注意力相关（AttentionPoint, AttentionEvent...）││
│  │   backtest.ts               - 回测相关（BacktestParams, BacktestResult...）  ││
│  │   scenario.ts               - 情景分析（ScenarioSummary, StateSnapshot...）  ││
│  │   news.ts                   - 新闻相关（NewsItem, NewsTrend...）             ││
│  │   index.ts                  - 统一导出                                       ││
│  │ web/types/ui.ts             - UI 状态类型（AsyncState, AsyncResult...）      ││
│  │ web/types/models.ts         - 原有类型（保持向后兼容）                        ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 各层职责

| 层级 | 职责 | 不应该做的 |
|------|------|-----------|
| **视图层** | 渲染 UI、响应用户交互 | 直接调用 API、复杂数据转换 |
| **容器组件** | 调用服务层、管理组件状态、处理加载/错误 | 直接调用 API |
| **Hooks 层** | 封装通用逻辑（异步、防抖等） | 业务逻辑、了解后端格式 |
| **服务层** | 调用 API、数据转换、业务规则 | UI 渲染、组件状态管理 |
| **API 层** | HTTP 请求、缓存、错误包装 | 业务逻辑、数据转换 |
| **类型层** | 类型定义 | 任何运行时逻辑 |

---

## 二、核心模块使用指南

### 2.1 useAsync Hook

统一的异步数据获取封装：

```tsx
import { useAsync, useAsyncCallback } from '@/lib/hooks';
import { priceService } from '@/lib/services';

// 自动获取数据（依赖变化时重新请求）
function PriceDisplay({ symbol }: { symbol: string }) {
  const { data, loading, error, refresh } = useAsync(
    () => priceService.getPriceData(symbol, '1D'),
    [symbol],
    { keepPreviousData: true }  // 切换 symbol 时保留旧数据
  );

  if (loading) return <LoadingSkeleton />;
  if (error) return <ErrorState message={error.message} onRetry={refresh} />;
  
  return <PriceChart data={data} />;
}

// 手动触发的操作
function BacktestForm() {
  const { execute, loading, error } = useAsyncCallback(
    (params) => backtestService.runBacktest(params)
  );

  const handleSubmit = async (formData) => {
    const result = await execute(formData);
    if (result) {
      // 处理结果
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* ... */}
      <button disabled={loading}>
        {loading ? 'Running...' : 'Run Backtest'}
      </button>
    </form>
  );
}
```

### 2.2 AsyncBoundary 组件

统一的加载/错误/空状态处理：

```tsx
import { AsyncBoundary } from '@/components/ui/async-boundary';

function MyComponent() {
  const { data, loading, error, refresh } = useAsync(...);

  return (
    <AsyncBoundary
      loading={loading}
      error={error}
      data={data}
      onRetry={refresh}
      loadingVariant="chart"
      loadingHeight={400}
      emptyFallback={<p>No data available</p>}
    >
      {(validData) => <Chart data={validData} />}
    </AsyncBoundary>
  );
}
```

### 2.3 服务层使用

```tsx
// 不要这样做（直接调用 API）
import { fetchPrice, fetchAttention } from '@/lib/api';
const price = await fetchPrice({ symbol: 'BTCUSDT', timeframe: '1d' });

// 应该这样做（通过服务层）
import { priceService, attentionService } from '@/lib/services';

// 获取价格数据（自动处理转换）
const priceSeries = await priceService.getPriceData('BTC', '1D');
// 返回类型: PriceSeries { symbol, timeframe, points, summary }

// 获取注意力数据
const attentionSeries = await attentionService.getAttentionData('BTC');
// 返回类型: AttentionSeries { symbol, granularity, points, summary }
```

---

## 三、迁移计划

### Phase 1: 基础设施（已完成 ✅）

- [x] 创建新的类型定义 (`types/models/`, `types/ui.ts`)
- [x] 创建通用 Hooks (`lib/hooks/useAsync.ts`)
- [x] 创建 AsyncBoundary 组件 (`components/ui/async-boundary.tsx`)
- [x] 创建服务层 (`lib/services/`)

### Phase 2: 核心组件迁移（已完成 ✅）

1. **高优先级** - 使用频率高，逻辑复杂
   - [x] `DashboardTab.tsx` - 使用服务层替换直接 API 调用 ✅
   - [ ] `BacktestPanel.tsx` - 待抽取回测逻辑到 `useBacktest` hook（延后，复杂度高）
   - [x] `AutoUpdateManager.tsx` - 已替换为服务层版本 ✅

2. **中优先级** - 独立模块，易于迁移
   - [x] `ScenarioTab.tsx` - 使用 scenarioService ✅
   - [x] `AttentionRegimePanel.tsx` - 使用 attentionService ✅
   - [ ] `MajorAssetModule.tsx` - 待使用 priceService + attentionService

3. **低优先级** - 相对简单，稳定
   - [x] `NewsService` - 已创建新闻服务层 ✅
   - [ ] `NewsList.tsx` - 可选择使用 newsService
   - [ ] `StatCards.tsx` - 保持现状或轻微调整
   - [ ] `PriceChart.tsx`, `AttentionChart.tsx` - 纯展示组件，无需改动

### Phase 3: 页面级重构（部分完成）

- [ ] `app/page.tsx` - 简化数据获取逻辑（可选优化）
- [x] `tabs/DashboardTab.tsx` - 已使用服务层和 AsyncBoundary ✅
- [x] `tabs/ScenarioTab.tsx` - 已使用 scenarioService ✅
- [ ] `tabs/MarketOverviewTab.tsx` - 待使用服务层

### Phase 4: 清理与优化（待进行）

- [ ] 移除 `lib/api.ts` 中的冗余类型定义
- [ ] 统一所有组件的错误处理风格
- [ ] 添加单元测试
- [ ] 清理备份文件 (*.old.tsx)

---

## 四、迁移示例

### 迁移 BacktestPanel

**迁移前**（直接调用 API，状态分散）：

```tsx
import { runBasicAttentionBacktest } from '@/lib/api';

function BacktestPanel() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await runBasicAttentionBacktest({ ...params });
      setResult(res);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  // ...
}
```

**迁移后**（使用服务层 + hooks）：

```tsx
import { useAsyncCallback } from '@/lib/hooks';
import { backtestService } from '@/lib/services';

function BacktestPanel() {
  const { execute, data: result, loading, error } = useAsyncCallback(
    (params) => backtestService.runBacktest(params)
  );

  async function run() {
    await execute(formParams);
  }
  // ...
}
```

### 迁移 ScenarioPanel

**迁移前**：

```tsx
import { fetchStateScenarios } from '@/lib/api';

function ScenarioPanel({ symbol }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadScenarios = async () => {
    setLoading(true);
    try {
      const res = await fetchStateScenarios({ symbol, ... });
      setData(res);
    } catch (e) {
      // 手动处理错误
    } finally {
      setLoading(false);
    }
  };
  // ...
}
```

**迁移后**：

```tsx
import { useAsync } from '@/lib/hooks';
import { scenarioService } from '@/lib/services';
import { AsyncBoundary } from '@/components/ui/async-boundary';

function ScenarioPanel({ symbol }) {
  const { data, loading, error, refresh } = useAsync(
    () => scenarioService.getScenarioAnalysis(symbol),
    [symbol]
  );

  return (
    <AsyncBoundary loading={loading} error={error} data={data} onRetry={refresh}>
      {(scenarios) => <ScenarioCards scenarios={scenarios} />}
    </AsyncBoundary>
  );
}
```

---

## 五、重构收益

### 代码质量

1. **减少重复逻辑** - 错误处理、加载状态在一处定义
2. **类型安全** - 领域模型类型贯穿整个应用
3. **易于测试** - 服务层可独立测试
4. **关注点分离** - 组件只关心渲染，服务只关心数据

### 开发体验

1. **一致的 API** - 所有数据获取使用相同模式
2. **自动状态管理** - useAsync 处理 loading/error/data
3. **统一 UI 反馈** - AsyncBoundary 提供一致的用户体验

### 可维护性

1. **新增功能更简单** - 添加新币种/时间周期只需修改服务层
2. **后端变更隔离** - API 格式变化只影响服务层
3. **易于扩展** - 添加缓存、日志、重试等横切关注点

---

## 六、注意事项

### 向后兼容

- 原有的 `lib/api.ts` 保持不变，现有代码可继续使用
- 新类型通过 `types/models/` 导出，不影响原有 `types/models.ts`
- 容器组件是可选的，原有组件可继续使用

### 性能考虑

- `useAsync` 支持 `staleTime` 避免重复请求
- `keepPreviousData` 在切换时保持 UI 稳定
- 服务层可添加缓存层进一步优化

### 渐进式迁移

- 不需要一次性迁移所有组件
- 可以逐个组件迁移，新旧代码可共存
- 建议从高频使用的组件开始
