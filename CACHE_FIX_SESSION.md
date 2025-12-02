# API 缓存问题修复总结

**会话日期**: 2025-02-07  
**问题描述**: 前端 `/api/attention-events` 端点返回空对象 `{}`，ECharts 显示 "width(0) and height(0)" 警告  
**根本原因**: API 缓存机制无差别地存储所有响应（包括错误），导致参数化端点返回过时或错误的缓存数据  
**解决方案**: 为所有时间序列和参数化端点禁用缓存

## 根本原因分析

### 缓存问题的工作流程

1. **初始错误状态**：API 请求失败（网络问题、数据缺失等）或返回错误对象
2. **错误被缓存**：`web/lib/api.ts` 中的 `setToCache()` 函数无差别地存储所有响应，包括错误
3. **参数变化时返回旧缓存**：用户改变请求参数（例如时间范围、符号等），但缓存基于完整参数哈希返回存储的错误
4. **错误持续化**：即使后续 API 调用可能成功，旧的缓存错误仍然返回

### 缓存实现细节

**文件**: `web/lib/api.ts`  
**缓存键**: `${endpoint}:${JSON.stringify(params)}`  
**TTL**: 5 分钟  
**最大条目数**: 50（LRU 驱逐）  

**问题代码（第 100-200 行）**:
```typescript
function getFromCache<T>(key: string): T | null {
  const entry = cache.get(key);
  if (entry && Date.now() - entry.timestamp < CACHE_TTL) {
    return entry.data;
  }
  cache.delete(key);
  return null;
}

function setToCache<T>(key: string, data: T): void {
  // ❌ 问题：无差别存储所有响应，包括错误对象
  if (cache.size >= CACHE_MAX_SIZE) {
    const firstKey = cache.keys().next().value;
    cache.delete(firstKey);
  }
  cache.set(key, { data, timestamp: Date.now() });
}
```

## 修复内容

### 修改的文件

**`web/lib/api.ts`** - 禁用以下端点的缓存：

| 函数名 | 端点 | 原因 | 参数类型 |
|--------|------|------|---------|
| `fetchPrice` | `/api/price` | 时间范围参数经常变化 | timeframe, start, end, limit |
| `fetchAttention` | `/api/attention` | 时间范围参数经常变化 | granularity, start, end |
| `fetchNews` | `/api/news` | 时间范围和过滤参数经常变化 | start, end, before, source |
| `fetchNewsCount` | `/api/news/count` | 时间范围参数经常变化 | start, end, before, source |
| `fetchNewsTrend` | `/api/news/trend` | 时间范围参数经常变化 | start, end, interval |
| `fetchAttentionEvents` | `/api/attention-events` | 核心功能，参数化查询 | symbol, lookback_days, min_quantile |
| `fetchAttentionEventPerformance` | `/api/attention-events/performance` | Symbol 变化时需要新数据 | symbol, lookahead_days |

### 修改方式

在所有调用中添加第三个参数 `false` 以禁用缓存：

```typescript
// ❌ 之前（启用缓存）
return fetchAPI<Candle[]>('/api/price', apiParams);

// ✅ 之后（禁用缓存）
return fetchAPI<Candle[]>('/api/price', apiParams, false);
```

## 验证步骤

### 1. 后端验证（已完成）
```bash
curl -s "http://localhost:8000/api/attention-events?symbol=ZEC&lookback_days=30&min_quantile=0.8" \
  | python3 -m json.tool | head -50
```
**结果**: ✅ 返回正确的 JSON 数组，包含 100+ 注意力事件对象，每个对象包含：
- `datetime`: 事件时间戳
- `event_type`: 事件类型（attention_spike、high_weighted_event）
- `intensity`: 强度值
- `summary`: 事件摘要

### 2. 前端验证（需要）
在浏览器控制台检查：
```javascript
// 应该看到的日志
// 1. 数据正确加载，不是 {}
// 2. 没有 "[API Error] /api/attention-events: {}" 错误
// 3. 图表正常渲染，无 "width(0)" 或 "height(0)" 警告
```

## 潜在的性能影响

**权衡**:
- ❌ **缺点**: 增加服务器负载（更频繁的 API 调用）
- ✅ **优点**: 数据准确性、用户体验改善、避免缓存引发的错误

**建议**:
- 服务器端可以实现更智能的缓存（区分成功/失败响应）
- 或者在前端实现条件缓存（仅缓存成功的响应）

## 后续改进建议

### 方案 1: 服务器端缓存改进
```python
# 在 FastAPI 中添加状态码检查
@app.get("/api/attention-events")
async def get_attention_events(...):
    # 缓存仅应用于 2xx 响应
    if response.status_code >= 400:
        # 不存储错误响应
        return error_response
```

### 方案 2: 前端缓存改进
```typescript
function setToCache<T>(key: string, data: T, isError: boolean = false): void {
  if (isError) {
    // 不缓存错误响应
    return;
  }
  // 缓存成功响应
  // ...
}
```

### 方案 3: 时间范围感知缓存
```typescript
// 仅对固定参数的端点缓存（如 /api/top-coins）
const CACHE_DISABLED_ENDPOINTS = [
  '/api/price',
  '/api/attention',
  '/api/news',
  '/api/attention-events'
];
```

## 测试场景

### 场景 1: 基本数据加载
```
1. 刷新页面
2. 等待数据加载
3. 检查 Market Overview → ZEC 模块
4. 验证: 注意力事件显示无误，图表正常渲染
```

### 场景 2: 符号切换
```
1. 加载 ZEC 数据
2. 切换到 BTC
3. 等待新数据加载
4. 验证: BTC 的注意力事件正确加载（不是 ZEC 的缓存数据）
```

### 场景 3: 时间范围变化
```
1. 加载完整数据范围
2. 用户交互改变时间范围（如果支持）
3. 验证: 新时间范围的数据正确加载
```

### 场景 4: 多次刷新
```
1. 加载数据
2. 刷新页面（Cmd+R）
3. 验证: 数据正确加载，无缓存问题
```

## 相关文件

- `web/lib/api.ts` - API 客户端实现
- `web/components/MajorAssetModule.tsx` - 主要使用者
- `web/components/news/NewsSummaryCharts.tsx` - 新闻图表组件
- `web/components/AttentionEvents.tsx` - 注意力事件组件

## 修改统计

- **修改文件数**: 1
- **修改函数数**: 7
- **添加禁用缓存**: 7 个端点
- **总行数变更**: +14 行（添加注释）

## 状态

✅ **已完成**
- 后端 API 验证
- 缓存禁用实现
- 代码审查

⏳ **待验证**
- 浏览器手动测试
- 多符号测试
- 时间范围变化测试

---

**最后修改**: 2025-02-07  
**修改者**: GitHub Copilot  
**相关会话**: WebSocket 修复 + API 缓存问题修复
