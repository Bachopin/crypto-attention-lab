# 自动更新机制说明

## 📋 核心逻辑

### 🆕 **新增代币初始化流程**

当您在前端"实时价格跟踪管理"中**启用自动更新**一个新代币时：

#### API 端点
```
POST /api/auto-update/enable
{
  "symbols": ["BTC", "ETH"]
}
```

#### 执行流程
1. **更新数据库标记**
   - 设置 `auto_update_price = True`
   - 设置 `is_active = True`
   - 如果代币不存在，自动创建新记录

2. **立即拉取历史价格**
   - 检查是否已有价格数据
   - 如果没有数据或数据过旧（>7天），拉取 **500天** 历史价格
   - 同时获取 `1d/4h/1h/15m` 四个时间粒度
   - 新币会自动拉取到上线日期为止

3. **立即计算 Attention Features**
   - 基于价格数据的完整时间范围
   - 自动从数据库查询相关新闻数据
   - 自动调用 Google Trends API 获取热度数据
   - Twitter 数据为 0（API 待实现）

#### 响应示例
```json
{
  "status": "success",
  "enabled": ["BTC", "ETH"],
  "initialized": ["BTC", "ETH"],
  "message": "Enabled and initialized 2/2 symbols"
}
```

### 🗑️ **移除代币**

当您不再需要跟踪某个代币时，可以将其移除：

#### API 端点
```
POST /api/auto-update/remove
{
  "symbols": ["BTC"]
}
```

#### 执行流程
1. **更新数据库标记**
   - 设置 `auto_update_price = False`
   - 设置 `is_active = False`
2. **保留历史数据**
   - 数据库中的价格和 Attention 数据**不会**被物理删除
   - 只是停止了后台的自动更新任务
   - 重新启用时可直接利用现有数据

#### 响应示例
```json
{
  "status": "success",
  "removed": ["BTC"],
  "message": "Disabled auto-update for 1 symbols"
}
```

---

### 🔄 **已有代币的持续维护**

系统通过 **后台定时任务** 维护数据，采用**多标的错峰更新**策略：

#### 1️⃣ **新闻更新任务** (`scheduled_news_update`)
- ⏰ **频率**: 每 1 小时
- 🎯 **范围**: 全局，不区分代币
- 📥 **行为**: 
  - 调用 `fetch_news_data.run_news_fetch_pipeline(days=1)`
  - 拉取最近 1 天的所有加密货币新闻
  - 存入数据库 `news_data` 表
  - 新闻带有 `symbols` 字段标识相关代币

#### 2️⃣ **价格 + Attention 更新任务** (`scheduled_price_update`)
- ⏰ **频率**: 每 **10 分钟**（可通过环境变量 `PRICE_UPDATE_INTERVAL` 配置）
- 🎯 **范围**: 所有 `auto_update_price=True` 的代币
- 📥 **行为**:
  
  **错峰更新策略**：
  - 多个标的在更新周期内**动态均匀分布**
  - 间隔计算公式：`(更新周期 × 0.8) / 标的数量`
  - 示例（10分钟周期）：
    - 5 个标的 → 每个间隔 96 秒
    - 10 个标的 → 每个间隔 48 秒
    - 20 个标的 → 每个间隔 24 秒
    - 30 个标的 → 每个间隔 16 秒
  - 预留 20% 时间作为缓冲，确保在下一周期前完成
  - 添加随机抖动避免完全同步
  
  **步骤 1: 更新价格数据**
  - 如果 `last_price_update` 为空 → 拉取 500 天历史数据
  - 如果 `last_price_update` 存在 → 增量拉取（最近 3-7 天）
  - 同时更新 `1d/4h/1h/15m` 四个时间粒度
  
  **步骤 2: 级联触发 Attention Features（带冷却期）**
  - 检查 `last_attention_update`：
    - 如果距上次更新 >= **1 小时** → 触发增量计算
    - 否则跳过，节省计算资源
  - 增量计算策略：
    - 获取数据库中最新的特征时间戳
    - 仅计算新数据（保留 45 天上下文用于滚动窗口）
    - 追加保存新特征（避免全量 upsert）
  
  **步骤 3: 级联触发 Google Trends（带冷却期）**
  - 检查 `last_google_trends_update`：
    - 如果距上次更新 >= **12 小时** → 允许调用 API
    - 否则使用缓存数据，避免 API 限流

---

## ⚙️ **配置参数**

所有更新相关的配置都在 `src/config/settings.py` 中：

| 参数 | 默认值 | 环境变量 | 说明 |
|------|--------|----------|------|
| `PRICE_UPDATE_INTERVAL` | 600s (10min) | `PRICE_UPDATE_INTERVAL` | 价格更新周期 |
| `FEATURE_UPDATE_COOLDOWN` | 3600s (1h) | `FEATURE_UPDATE_COOLDOWN` | 特征值更新冷却期 |
| `GOOGLE_TRENDS_COOLDOWN` | 43200s (12h) | `GOOGLE_TRENDS_COOLDOWN` | Google Trends 更新冷却期 |
| `ROLLING_WINDOW_CONTEXT_DAYS` | 45 | - | 增量计算保留的上下文天数 |

---

## 🔑 **关键设计原则**

### ✅ **增量计算优化**
- **特征值增量计算**：仅计算最新的数据，避免全量重算
- **滚动窗口上下文**：保留 45 天历史数据用于 z-score 等计算
- **冷却期过滤**：避免频繁重复计算
- **事件预计算**：特征值更新时同步计算并存储注意力事件（`detected_events` 字段）

### ✅ **注意力事件缓存策略**
- **预计算存储**：特征值计算时自动检测事件（`lookback_days=30`, `min_quantile=0.8`）
- **按需更新**：API 请求时如果没有预计算事件，自动触发增量计算
- **条件缓存**：仅默认参数使用缓存，自定义参数实时计算确保准确性

### ✅ **多标的错峰更新**
- 在更新周期内**均匀分布**各标的的更新时间
- 添加随机抖动避免完全同步
- 减少 API 限流风险

### ✅ **级联更新链**
```
价格更新 ──────────────────────────────────────────────────────┐
    ↓                                                          │
特征值更新（冷却期过滤）                                         │
    ↓                                                          │
Google Trends 更新（冷却期过滤）                                 │
    ↓                                                          │
预计算更新（EventPerformance + StateSnapshots）                  │
    ↓                                                          │
WebSocket 广播（如有订阅者）                                     │
    ↓                                                          │
等待下一个标的 ──→ 延迟（错峰间隔） ──→ 循环处理下一个标的 ────────┘
```

### ✅ **预计算存储策略**
系统预计算并存储以下静态/准静态数据，减少 API 请求时的实时计算开销：

| 预计算类型 | 存储位置 | 更新策略 | 冷却期 | 缓存参数 |
|-----------|---------|----------|-------|---------|
| `event_performance` | Symbol 表 `event_performance_cache` | 冷却期控制 | **12小时** | `lookahead_days=[1,3,5,10]` |
| `state_snapshots (1d)` | `state_snapshots` 表 | 冷却期控制 | **24小时** | `window_days=30` |
| `state_snapshots (4h)` | `state_snapshots` 表 | 冷却期控制 | **4小时** | `window_days=30` |

**触发机制：**
- **全量特征更新** → `force_refresh=True` → 强制重算所有预计算
- **增量特征更新** → `force_refresh=False` → 
  - `event_performance`: 检查冷却期（12h），过期则重算
  - `state_snapshots (1d)`: 检查冷却期（24h），过期则增量计算
  - `state_snapshots (4h)`: 检查冷却期（4h），过期则增量计算
- **API 请求时无缓存** → 按需触发计算并存储

**非默认参数实时计算：**
- `event_performance`: 非 `[1,3,5,10]` 的 `lookahead_days` 实时计算
- `state_snapshots`: 非 `30` 的 `window_days` 实时计算

### ✅ **被动数据获取**
- **Google Trends** 和 **Twitter** 数据由 Attention 计算触发
- 不需要独立的定时任务
- 通过冷却期控制调用频率

### ✅ **新闻数据池化**
- 新闻数据是**全局性**的，不区分代币
- 所有新闻统一存储在数据库中
- 计算 Attention 时按 `symbols` 字段过滤
- 新增代币可以利用历史新闻数据
- **支持 Ticker + 映射名称搜索**（如 ZEC + Zcash）

---

## 📊 **数据流示意图**

```
┌─────────────────────────────────────────────────────────────┐
│ 后台定时任务（每 10 分钟）                                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 获取所有 auto_update=True 的标的                              │
│ 标的列表: [BTC, ETH, SOL, ZEC, ...]                          │
│ 动态计算间隔: (600s × 0.8) / N 个标的                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ For each symbol (动态间隔):                                   │
│                                                              │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ 1. 更新价格数据（增量：最近3-7天）                      │   │
│ └──────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ 2. 检查特征值冷却期（1h）                               │   │
│ │    ├─ 已过冷却期 → 增量计算特征值                       │   │
│ │    │   ├─ 检查 Google Trends 冷却期（12h）             │   │
│ │    │   │   ├─ 已过 → 调用 API 更新                     │   │
│ │    │   │   └─ 未过 → 使用缓存                          │   │
│ │    │   ├─ Twitter = 0（API 待实现）                    │   │
│ │    │   └─ 保存新增特征                                 │   │
│ │    └─ 未过冷却期 → 跳过                                 │   │
│ └──────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│ ┌──────────────────────────────────────────────────────┐   │
│ │ 3. WebSocket 广播（如有订阅者）                         │   │
│ └──────────────────────────────────────────────────────┘   │
│                          ↓                                  │
│         等待动态间隔后处理下一个标的                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🏷️ **代币别名获取（带备用方案）**

新代币启用时，系统会自动获取代币名称和别名，用于新闻搜索和 Google Trends 关键词：

```
fetch_symbol_aliases_with_fallback('HYPE')
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 方案1: CoinGecko（最完整）                                    │
│   ├─ 成功 → 返回 name, id, aliases                           │
│   └─ 失败/限流 → 尝试方案2                                    │
├─────────────────────────────────────────────────────────────┤
│ 方案2: CryptoCompare（备用，限流宽松）                         │
│   ├─ 成功 → 返回 name, id, aliases                           │
│   └─ 失败 → 尝试方案3                                        │
├─────────────────────────────────────────────────────────────┤
│ 方案3: Binance（验证存在性）                                  │
│   ├─ 成功 → 返回 symbol, aliases                             │
│   └─ 失败 → 使用兜底                                         │
├─────────────────────────────────────────────────────────────┤
│ 兜底: 使用符号本身                                            │
│   返回 'HYPE', None, 'HYPE,hype'                             │
└─────────────────────────────────────────────────────────────┘
```

**别名用途：**
- **新闻搜索**：`News.title.ilike('%HYPE%') OR News.title.ilike('%Hyperliquid%')`
- **Google Trends**：`keywords=['HYPE', 'Hyperliquid', 'hyperliquid']`
- **Twitter 查询**：`$HYPE OR HYPE OR Hyperliquid`

---

## 🛠️ **手动触发 API**

### 刷新单个代币（推荐）
```bash
POST /api/refresh-symbol?symbol=BTC&check_completeness=true
```
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `symbol` | 必填 | 代币符号（如 BTC, HYPE） |
| `check_completeness` | `true` | 是否检查数据完整性并自动补全 |

功能：
- 检查数据完整性（默认开启）
- 自动补全缺失的历史数据（如完整性 < 95%）
- 抓取最新价格
- 重新计算 Attention Features

### 手动触发价格更新（旧接口）
```bash
POST /api/auto-update/trigger
{
  "symbols": ["BTC", "ETH"]
}
```
- 立即拉取最新价格
- **不会**自动计算 Attention（仅价格更新）

### 手动触发 Attention 计算
```bash
POST /api/attention/trigger-update
{
  "symbols": ["BTC", "ETH"],  # 可选，不指定则更新所有启用的代币
  "freq": "D"                 # 可选，默认 "D"，可选 "4H"
}
```
- 立即重新计算 Attention Features
- 使用增量模式（仅计算新数据）

---

## 📝 **重要说明**

### ✅ 数据完整性检查
系统会智能判断是否需要检查数据完整性：
- **首次更新**（`last_update` 为空）：强制检查
- **超过 24 小时未更新**：触发检查
- **正常 10 分钟周期**：跳过检查，直接增量更新（节省资源）
- **手动刷新**：默认开启完整性检查

完整性检查策略：
- 计算数据点数量与预期值的比例（95% 阈值）
- 检查最早数据是否覆盖到预期范围
- 如果完整性不足，自动触发全量回填

### ✅ 增量 vs 全量计算
当前实现支持**增量计算**：
- 检查数据库中最新的特征时间戳
- 仅计算该时间戳之后的新数据
- 保留 45 天历史上下文用于滚动窗口计算
- 追加保存新特征，避免全量 upsert

首次计算或数据缺失时自动回退到全量模式。

### ✅ Google Trends API 限制
- 单次请求 ≤269 天返回日级数据，>269 天返回周级数据
- 已实现自动分段拉取，确保日级粒度
- 存在速率限制，通过 **12 小时冷却期** 控制
- 多标的**错峰更新**避免同时请求
- 关键词使用 **Ticker + 映射名称**（如 `["Zcash", "ZEC"]`）
- 多关键词结果取**最大值**反映峰值关注度

### ⚠️ Twitter 数据待实现
- 当前返回 0（不再使用 mock 数据）
- 待集成 Twitter API 后可自动获取真实数据
- 逻辑流程已预留，无需改动框架

### ✅ Binance 现货/合约自动切换
- 系统会自动检测代币在 Binance 的上市情况
- 优先使用现货（Spot）API：`https://api.binance.com/api/v3`
- 如果代币只在合约市场上市（如 HYPE），自动切换到合约（Futures）API：`https://fapi.binance.com/fapi/v1`
- 检测结果会被缓存，避免重复请求

---

## 📌 **与原设计的对比**

| 项目 | 旧设计 | 新设计 | 状态 |
|------|--------|--------|------|
| 新增代币初始化 | 仅标记，等待定时任务 | 立即拉取+计算 | ✅ 已实现 |
| 价格更新频率 | 每 2 分钟 | 每 10 分钟（可配置） | ✅ 已优化 |
| 多标的更新 | 顺序更新 | 错峰更新（均匀分布） | ✅ 已优化 |
| Attention 更新 | 每次价格更新后立即触发 | 带冷却期（1h）触发 | ✅ 已优化 |
| Attention 计算 | 全量重算 | 增量计算 | ✅ 已优化 |
| Google Trends | 每次 Attention 都调用 | 12h 冷却期控制 | ✅ 已优化 |
| Twitter Volume | mock 数据 | 返回 0（API 待实现） | ✅ 已修正 |
| 新闻数据拉取 | 全局定时任务（1小时） | 全局定时任务（1小时） | ✅ 保持 |
| Binance API | 仅现货 | 现货 + 合约自动切换 | ✅ 已实现 |
| 数据完整性检查 | 无 | 智能检查 + 自动回填 | ✅ 已实现 |
| 手动刷新 | 全局更新 | 单代币刷新 + 完整性检查 | ✅ 已实现 |

---

## 🚀 **使用示例**

### 前端启用新代币
```typescript
// web/components/AutoUpdateManager.tsx
const enableAutoUpdate = async (symbol: string) => {
  const res = await fetch(`${apiBaseUrl}/api/auto-update/enable`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbols: [symbol] })
  });
  
  const result = await res.json();
  // result.initialized 包含成功初始化的代币列表
  console.log(`Initialized: ${result.initialized.join(', ')}`);
}
```

### 查看后台任务日志
```bash
# 启动 API 后查看日志
[Scheduler] Background tasks started: news_update (hourly), price_update (10min)
[Scheduler] Attention features will be calculated with 1h cooldown

# 价格更新周期（每10分钟，错峰更新）
[Updater] Updating 5 symbols (interval: 600s)...
[Updater] [1/5] Processing BTC...
[Updater]   BTC 1d: 7 records saved
[Updater] Calculating attention features for BTC (Google Trends: skip)...
[Updater] ✅ Attention features updated for BTC
# ... 等待 ~1.5min ...
[Updater] [2/5] Processing ETH...
[Updater] Skipping attention for ETH (cooldown: 45min remaining)
# ...
[Updater] Update cycle completed

# 新闻更新周期（每1小时）
[Scheduler] Starting hourly news update...
[NewsFetcher] Fetched 150 news articles
[Scheduler] News update completed
```

### 环境变量配置
```bash
# .env
PRICE_UPDATE_INTERVAL=600          # 10分钟
FEATURE_UPDATE_COOLDOWN=3600       # 1小时
GOOGLE_TRENDS_COOLDOWN=43200       # 12小时
```

---

**最后更新**: 2025-11-30  
**版本**: v3.2 - 增量计算 + 错峰更新 + 冷却期控制 + 事件预计算 + 预计算存储

````
