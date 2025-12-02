# Crypto Attention Lab - 注意力因子与策略指南

## 📋 目录
- [系统架构](#系统架构)
- [数据流程](#数据流程)
- [注意力特征详解](#注意力特征详解)
- [事件检测机制](#事件检测机制)
- [基础策略说明](#基础策略说明)
- [API 使用指南](#api-使用指南)
- [前端交互](#前端交互)
- [扩展方向](#扩展方向)
- [State Snapshot（状态快照）](#state-snapshot状态快照)
- [相似状态检索（Similar States）](#相似状态检索similar-states)
- [Attention Scenario Engine（情景分析引擎）](#attention-scenario-engine情景分析引擎)

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      数据采集层                              │
│  CryptoPanic | NewsAPI | CryptoCompare | RSS Feeds         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   服务编排层 (Service Layer)                 │
│  attention_service.py: 协调数据加载、计算与存储               │
│  market_data_service.py: 统一价格与注意力数据对齐             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   纯逻辑计算层 (Pure Logic)                  │
│  calculators.py: 纯数学计算，无 I/O                          │
│  news_features.py: 文本特征提取                              │
│  attention_events.py: 纯逻辑事件检测                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  事件检测 & 策略层                           │
│  basic_attention_factor.py: 简单加权注意力策略              │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      API 层                                  │
│  FastAPI: /api/attention-events, /api/backtest/...         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   前端可视化层                               │
│  Next.js: 事件标注 + 回测面板 + 交互式参数调节              │
└─────────────────────────────────────────────────────────────┘
```

---

## 数据流程

### 1. 原始新闻采集
```bash
python scripts/fetch_news_data.py
```
- 从多个来源聚合新闻（CryptoPanic、CryptoCompare、NewsAPI、RSS）
- 自动去重、过滤相关性
- 保存到 `data/raw/attention_zec_news.csv` 和数据库

**注意力数据时间区间对齐机制：**
- 所有注意力相关数据（Google Trends、Twitter Volume 等）自动以价格数据区间为准
- 新币种加入时，自动拉取与价格数据相同时间跨度的历史数据
- 确保多通道注意力特征的时间一致性

### 2. 新闻特征计算
位置：`src/features/news_features.py`

每条新闻计算以下特征：
```python
source_weight(source: str) -> float
# CoinDesk=1.0, Cointelegraph=0.9, CryptoPanic=0.8, ...

sentiment_score(title: str) -> float
# -1.0 ~ 1.0，基于正负关键词

extract_tags(title: str) -> List[str]
# listing, hack, upgrade, partnership, regulation

relevance_flag(title: str, symbol: str) -> str
# direct 或 related
```

### 3. 日级注意力特征聚合
```bash
python scripts/generate_attention_data.py
```

位置：`src/services/attention_service.py` (编排) & `src/features/calculators.py` (计算)

从新闻级特征聚合为日级（核心逻辑在 `calculators.calculate_composite_attention`）：
```python
attention_score = min_max_normalize(news_count, 0-100)
weighted_attention = sum(source_weight * relevance_weight)
bullish_attention = sum(positive_sentiment * weighted)
bearish_attention = sum(negative_sentiment * weighted)
event_intensity = has_high_weight_source AND strong_sentiment AND has_tags ? 1 : 0
```

保存到 `data/processed/attention_features_zec.csv` 和数据库。

👉 **2025 版更新**：引入了 `AttentionService` 来统一管理数据流。它会调用
`google_trends_fetcher` 与 `twitter_attention_fetcher`，并使用纯函数 `calculators.py`
基于 `src/config/attention_channels.py` 中的配置生成三条通道（新闻、Google
Trends、Twitter）与 `composite_attention_score`。

### 3b. Google Trends 同步（2025 新增）
```bash
python scripts/fetch_multi_symbol_google_trends.py --days 365
```
- 根据 `TRACKED_SYMBOLS` 与数据库中的可用币种，批量抓取 Google 搜索热度；
- 通过 `pytrends` 获取真实 interest-over-time 序列；不再写入独立表（`google_trends` 已废弃），
  直接作为外部通道输入参与 `attention_features` 计算；不可用时记录 warning 并退化为 0。

### 4. 事件检测
位置：`src/events/attention_events.py`

该模块已重构为**纯逻辑库**，核心函数 `compute_attention_events` 接收 DataFrame 并返回事件列表，不再直接操作数据库。API 层通过 `MarketDataService` 获取对齐数据后调用此逻辑。

基于滚动分位数阈值检测异常事件：
```python
if weighted_attention >= quantile(weighted_attention, lookback_days, 0.8):
    → high_weighted_event

if bullish_attention >= quantile(bullish_attention, lookback_days, 0.8):
    → high_bullish

# 类似逻辑用于 high_bearish、attention_spike、event_intensity
```

### 5. 策略回测
位置：`src/backtest/basic_attention_factor.py`

简单策略示例：
```python
# 入场条件
if (
    weighted_attention >= quantile(weighted_attention, lookback_days, 0.8) and
    daily_return <= max_daily_return and
    bullish_attention > bearish_attention
):
    buy_at_close()
    hold_for(holding_days)
    sell_at_close()

# 统计
win_rate = wins / total_trades
avg_return = mean(returns)
max_drawdown = max(peak - equity) / peak
```

🧪 **快速对比脚本**：
```bash
python scripts/demo_multi_symbol_attention_backtest.py
```
输出 Legacy vs Composite 两套信号在 `ZEC/BTC/ETH` 上的收益对比，可做日常 sanity check。

---

## 注意力特征详解

### 基础特征
| 字段 | 含义 | 取值范围 | 计算方式 |
|------|------|----------|----------|
| `news_count` | 当日新闻数量 | ≥0 | 直接计数 |
| `attention_score` | 标准化注意力分数 | 0-100 | min-max 归一化 |

### 扩展特征
| 字段 | 含义 | 取值范围 | 计算方式 |
|------|------|----------|----------|
| `weighted_attention` | 加权注意力 | ≥0 | Σ(source_weight × relevance_weight) |
| `bullish_attention` | 看涨注意力 | ≥0 | Σ(positive_sentiment × weighted) |
| `bearish_attention` | 看跌注意力 | ≥0 | Σ(negative_sentiment × weighted) |
| `event_intensity` | 事件强度标记 | 0/1 | 高权重来源 ∧ 强情绪 ∧ 有标签 |

### 多通道 Attention（2025 版新增）

| 字段 | 通道 | 含义 | 备注 |
|------|------|------|------|
| `news_channel_score` | 新闻 | `weighted_attention` 的滚动 z-score | 反映加权新闻热度的堆积/衰退 |
| `google_trend_value` / `google_trend_zscore` / `google_trend_change_7d` / `google_trend_change_30d` | Google Trends | 搜索热度及其变化 | 由 `pytrends` 获取，关键词配置见 `attention_channels.py` |
| `twitter_volume` / `twitter_volume_zscore` / `twitter_volume_change_7d` | Twitter | 公开推文讨论量 | 调用官方 counts API（无 Token 时自动回退为 0） |
| `composite_attention_score` / `composite_attention_zscore` | 合成 | `news + google + twitter` 的线性组合 | 默认权重 0.5 / 0.3 / 0.2，可配置 |
| `composite_attention_spike_flag` | 合成 | 合成得分是否超过滚动 90% 分位 | 用于趋势/扩散诊断 |

上述字段都存储在 `attention_features` 表并通过 `/api/attention`
返回，可作为多日趋势策略的统一入口。

Google 通道的关键补充：
- 可执行 `scripts/fetch_multi_symbol_google_trends.py --force-refresh` 强制刷新任意窗口；
- 如果网络/配额暂不可用，后端会退化为 0 并打印 warning，方便排查；
- 不再写入独立表；可选启用 CSV 缓存，或直接实时拉取用于计算。

### 3c. 数据对齐与服务 (Data Alignment Service)
位置：`src/services/market_data_service.py`

为了确保回测与研究模块使用的数据一致性，引入了 `MarketDataService`：
- **统一接口**：`get_aligned_data(symbol, ...)`
- **自动对齐**：以价格数据（OHLCV）的时间戳为基准，左连接（Left Join）注意力数据
- **缺失值处理**：自动处理非交易日或缺失的注意力数据（ffill/0填充）
- **时区标准化**：强制统一为 UTC 时间

整体计算流程：
1. `attention_fetcher` 收集多来源新闻并写入语言/平台元数据；
2. `news_features` 结合 `attention_channels.py` 的语言/来源/节点配置计算加权新闻热度；
3. `google_trends_fetcher` 与 `twitter_attention_fetcher` 依据同一配置抓取并缓存外部信号；
4. `AttentionService` 协调数据加载，调用 `calculators.calculate_composite_attention` 汇总所有通道，按配置权重产出 `composite_attention_score` 及 z-score/flag；
5. API 层直接暴露每个通道与合成指标，方便前端或量化脚本使用。

> ⚠️ 若未配置 Google/Twitter 凭证，系统会自动记录 0 并继续执行，确保回测/离线生成流程不被阻塞。

### 来源权重表

**设计原则**：中文新闻源权重与英文新闻源相当，确保多语言新闻的公平性。

```python
SOURCE_BASE_WEIGHTS = {
    # 顶级新闻源 (权重 1.0)
    "PANews": 1.0,           # 中文顶级（数据库中 5 万+ 条）
    "CoinDesk": 1.0,         # 英文顶级
    
    # 一线新闻源 (权重 0.92-0.95)
    "金色财经": 0.95,         # 中文一线
    "Cointelegraph": 0.95,   # 英文一线
    "Odaily": 0.92,          # 中文二线
    "The Block": 0.92,       # 英文二线
    
    # 二线新闻源 (权重 0.85-0.88)
    "巴比特": 0.88,           # 中文
    "Decrypt": 0.88,         # 英文
    "链捕手": 0.85,           # 中文
    "BeInCrypto": 0.85,      # 英文
    
    # 三线及聚合源 (权重 0.65-0.80)
    "CryptoPanic": 0.80,     # 聚合平台
    "cryptopolitan": 0.75,   # 英文三线
    "bitcoinist": 0.75,
    "CryptoCompare": 0.70,   # 数据平台
    "CryptoSlate": 0.65,
    
    # 其他
    "RSS": 0.55,
    "Unknown": 0.50,
}
```

**语言权重**：
- 中文 (`zh`): 1.0
- 英文 (`en`): 1.0
- 其他语言: 0.6-0.75

**最终权重计算**：
```
effective_weight = source_base_weight × language_weight × node_adjustment (可选)
```

**示例**：
- PANews (中文): 1.0 × 1.0 = **1.0**
- CoinDesk (英文): 1.0 × 1.0 = **1.0**
- 金色财经 (中文): 0.95 × 1.0 = **0.95**
- Cointelegraph (英文): 0.95 × 1.0 = **0.95**

### 情绪关键词
```python
POSITIVE_WORDS = ["surge", "rally", "bullish", "partnership", "upgrade", "record", "soar", "gain"]
NEGATIVE_WORDS = ["hack", "exploit", "breach", "lawsuit", "fall", "drop", "bearish", "plunge"]
```

### 主题标签
```python
KEYWORD_TAGS = {
    "listing": ["listing", "list on", "added to", "listed"],
    "hack": ["hack", "exploit", "breach"],
    "upgrade": ["upgrade", "update", "hard fork", "fork", "release"],
    "partnership": ["partnership", "partner", "collaboration"],
    "regulation": ["regulation", "sec", "lawsuit", "fine"],
}
```

---

## 事件检测机制

### 检测算法
使用**滚动分位数阈值**识别显著变化：

```python
# 伪代码
for each day:
    lookback_window = past_N_days
    threshold = quantile(lookback_window, min_quantile)  # 默认 0.8
    
    if current_value >= threshold:
        emit_event(type, intensity=current_value - threshold)
```

### 事件类型
| 事件类型 | 触发条件 | 含义 |
|----------|----------|------|
| `attention_spike` | `attention_score` 超过分位数 | 注意力突增 |
| `high_weighted_event` | `weighted_attention` 超过分位数 | 综合加权注意力高 |
| `high_bullish` | `bullish_attention` 超过分位数 | 看涨情绪浓厚 |
| `high_bearish` | `bearish_attention` 超过分位数 | 看跌情绪浓厚 |
| `event_intensity` | `event_intensity == 1` | 高质量复合事件 |

### 参数说明
- `lookback_days`（默认 30）：计算分位数的回溯窗口
- `min_quantile`（默认 0.8）：分位数阈值（80% 分位数）

**调优建议**：
- 增大 `lookback_days` → 更平滑的阈值，降低假信号
- 提高 `min_quantile` → 更严格的条件，减少事件数量
- 降低 `min_quantile` → 更敏感的检测，增加事件捕获

---

## 基础策略说明

### 策略逻辑（S1 示例）

**入场条件**：
1. `weighted_attention >= quantile(weighted_attention, lookback_days, attention_quantile)`
2. `daily_return <= max_daily_return`（避免追高）
3. `bullish_attention > bearish_attention`（看涨情绪占优）

**持仓管理**：
- 收盘价买入
- 持有 `holding_days` 天
- 到期收盘价卖出

**风险提示**：
⚠️ **本策略为实验性质，不构成投资建议！**
- 无止损机制
- 全仓进出
- 未考虑交易成本
- 历史表现不代表未来

### 参数说明

| 参数 | 默认值 | 含义 | 调优方向 |
|------|--------|------|----------|
| `lookback_days` | 30 | 分位数回溯窗口 | ↑ 更稳定，↓ 更敏感 |
| `attention_quantile` | 0.8 | 入场阈值（分位数） | ↑ 更严格，↓ 更频繁 |
| `max_daily_return` | 0.05 | 当日最大涨幅（5%） | ↑ 允许追高，↓ 更保守 |
| `holding_days` | 3 | 持仓天数 | ↑ 长期，↓ 短期 |

### 回测输出

**Summary 统计**：
```json
{
  "total_trades": 4,
  "win_rate": 50.0,
  "avg_return": 0.0021,
  "cumulative_return": 0.0086,
  "max_drawdown": 0.031
}
```

**Trade 列表**：
```json
[
  {
    "entry_date": "2024-03-15",
    "exit_date": "2024-03-18",
    "entry_price": 28.34,
    "exit_price": 28.78,
    "return_pct": 0.0155
  }
]
```

**Equity Curve**：
```json
[
  {"datetime": "2024-03-15", "equity": 1.0021},
  {"datetime": "2024-03-18", "equity": 1.0155}
]
```

---

## API 使用指南

### 1. 获取注意力事件
```http
GET /api/attention-events?symbol=ZEC&lookback_days=30&min_quantile=0.8&start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z
```

**响应示例**：
```json
[
  {
    "datetime": "2024-03-15T00:00:00Z",
    "event_type": "high_weighted_event",
    "intensity": 0.92,
    "summary": "news_count=22, att=100.0, w_att=14.6, bull=1.45, bear=0.6"
  }
]
```

### 2. 运行回测
```http
POST /api/backtest/basic-attention
Content-Type: application/json

{
  "symbol": "ZECUSDT",
  "lookback_days": 30,
  "attention_quantile": 0.8,
  "max_daily_return": 0.05,
  "holding_days": 3,
  "start": "2024-01-01T00:00:00Z",
  "end": "2024-12-31T23:59:59Z"
}
```

**响应示例**：见上文 "回测输出" 部分。

### 3. 获取扩展新闻特征
```http
GET /api/news?symbol=ZEC
```

**响应示例**：
```json
[
  {
    "datetime": "2024-01-01T10:30:00Z",
    "source": "CryptoPanic",
    "title": "ZEC Price Surges on Privacy Upgrade",
    "url": "https://...",
    "relevance": "direct",
    "source_weight": 1.2,
    "sentiment_score": 0.6,
    "tags": "upgrade,privacy"
  }
]
```

### 4. 获取扩展注意力特征
```http
GET /api/attention?symbol=ZEC&granularity=1d
```

**响应示例**：
```json
[
  {
    "timestamp": 1704067200000,
    "datetime": "2024-01-01T00:00:00Z",
    "attention_score": 67.5,
    "news_count": 12,
    "weighted_attention": 14.6,
    "bullish_attention": 1.45,
    "bearish_attention": 0.60,
    "event_intensity": 0
  }
]
```

---

## 前端交互

### 价格图表事件标注
- **位置**：K 线图上方/下方
- **样式**：
  - `high_bullish` → 绿色向上箭头 ↑
  - `high_bearish` → 红色向下箭头 ↓
  - `high_weighted_event` → 蓝色圆点
  - `attention_spike` → 黄色圆点
  - `event_intensity` → 黄色圆点

- **控制**：右上角 "事件标注：开/关" 按钮

### 事件列表面板
- **位置**：主页中部，左侧区域
- **内容**：所有检测到的事件，按时间倒序
- **详情**：日期、类型、强度、新闻摘要

### 回测面板
- **位置**：主页中部，右侧区域
- **参数调节**：
  - Lookback：回溯天数（默认 30）
  - Quantile：分位数阈值（默认 0.8）
  - Max Daily Ret：最大日涨幅（默认 0.05）
  - Holding Days：持仓天数（默认 3）
- **运行按钮**：点击 "Run Backtest" 触发回测
- **结果展示**：
  - Summary 统计卡片（5 个）
  - 详细交易表格（可滚动）

---

## 扩展方向

### 短期改进（1-2 周）
1. **止损/止盈机制**：在策略中添加风险控制逻辑
2. **仓位管理**：支持分批建仓、固定比例仓位
3. **交易成本**：计算手续费/滑点对收益的影响
4. **更多策略**：基于 `bullish_attention / bearish_attention` 的反向策略
5. **前端 Equity Curve 图表**：在回测面板中绘制资金曲线

### 中期扩展（1-2 月）
1. **多币种支持**：扩展到 BTC、ETH 等主流币
2. **实体识别（NER）**：从新闻中提取具体人物/机构/事件
3. **KOL 影响力分析**：跟踪推特大 V 的发言与价格相关性
4. **事件链路追踪**：同一主题的多条新闻聚合为事件链
5. **机器学习模型**：LSTM/Transformer 预测注意力 → 价格

### 节点带货能力因子（Node Carry Factor）🆕

在原有「按标的聚合的注意力因子」之上，本项目引入了**节点级带货能力因子**，用于刻画某个传播节点在触发注意力事件后，对未来价格收益的平均贡献。

#### 节点与节点 ID 定义

- **platform**：平台类别，目前主要为 `"news"`（新闻/聚合）、`"social"`（社交）、`"rss"` 等；
- **node**：传播节点标识，优先使用 `author/account`，否则回退为 `source`；
- **node_id**：统一的节点 ID，当前规则为：

  ```python
  node_id = f"{platform}:{node}"
  ```

例如：`"news:CoinDesk"`、`"social:Twitter"`。

抓取层在 `src/data/attention_fetcher.py` 中已经补充了 `platform` / `author` / `node` / `node_id` 字段（对于不支持的源则退化为 `None` 或 `source`）。

#### 节点级注意力特征

模块：`src/features/node_attention_features.py`

核心函数：

```python
from src.features.node_attention_features import build_node_attention_features

df_node = build_node_attention_features(symbol="ZEC", freq="D")
``

返回的 DataFrame 列包括：

- `symbol`, `node_id`, `datetime`, `freq`
- `news_count`
- `weighted_attention`
- `bullish_attention`, `bearish_attention`
- `sentiment_mean`, `sentiment_std`

特征构造与标的级注意力特征保持一致，只是按 `(symbol, node_id, datetime)` 粒度聚合。

#### 节点带货能力因子

模块：`src/features/node_influence.py`

核心接口：

```python
from src.features.node_influence import compute_node_carry_factor

df = compute_node_carry_factor(symbol="ZEC", lookahead="1d", lookback_days=180)
```

计算逻辑（简化描述）：

1. 使用 `detect_attention_events` 获取标的级注意力事件（如 `high_weighted_event` 等）；
2. 在节点级注意力特征里，找到**事件当日有贡献的节点集合**；
3. 对每个节点，在其参与事件的所有时间点上，计算未来 `lookahead` 天的价格对数收益；
4. 按节点聚合收益路径，得到：
   - `mean_excess_return`：平均收益（当前实现中等同于绝对平均收益，未来可替换为相对基准超额收益）；
   - `hit_rate`：收益 > 0 的比例；
   - `ir`：信息比率 $\text{IR} = \frac{\mu}{\sigma}$；
   - `n_events`：该节点参与的事件样本数。

输出 DataFrame 示例结构：

| symbol | node_id          | n_events | mean_excess_return | hit_rate | ir  | lookahead | lookback_days |
|--------|------------------|----------|---------------------|----------|-----|-----------|---------------|
| ZEC    | news:CoinDesk    | 42       | 0.012              | 0.64     | 1.8 | 1d        | 365           |

#### 节点因子查询 API

后端在 `src/api/main.py` 中暴露了新的查询接口：

```http
GET /api/node-influence?symbol=ZEC&min_events=10&sort_by=ir&limit=100
```

请求参数：

- `symbol`：可选，指定标的（如 `ZEC`），为空则返回所有标的；
- `min_events`：最小事件样本数量过滤，默认 10；
- `sort_by`：排序字段，支持 `ir` / `mean_excess_return` / `hit_rate`，默认 `ir`；
- `limit`：返回记录数上限，默认 100。

响应示例：

```json
[
  {
    "symbol": "ZEC",
    "node_id": "news:CryptoPanic",
    "n_events": 42,
    "mean_excess_return": 0.012,
    "hit_rate": 0.64,
    "ir": 1.8,
    "lookahead": "1d",
    "lookback_days": 365
  }
]
```

#### Python 使用示例

```python
from src.features.node_influence import compute_node_carry_factor

df = compute_node_carry_factor(symbol="ZEC", lookahead="1d", lookback_days=180)
print(df.sort_values("ir", ascending=False).head(10))
```

更多脚本示例可见：`scripts/compute_node_influence_example.py`。

### 长期目标（3-6 月）
1. **实时 WebSocket 流**：毫秒级价格 + 新闻推送
2. **多因子融合**：注意力 + 技术指标 + 链上数据
3. **自动化信号推送**：Telegram/Discord/Email 实盘提醒
4. **社区版策略市场**：用户分享/订阅策略配置
5. **云端部署**：Docker + K8s + CI/CD 自动化

---

## 常见问题

### Q1: 数据库和 CSV 如何切换？
**A**: 在 `src/data/db_storage.py` 中设置 `USE_DATABASE = True/False`。  
- `True`：优先使用 SQLite 数据库（推荐）
- `False`：回退到 CSV 文件模式

### Q2: 如何添加新币种？
**A**: 
1. 修改 `scripts/fetch_news_data.py` 和 `fetch_price_data.py` 的 `symbol` 参数
2. 运行数据采集脚本
3. 运行 `scripts/migrate_to_database.py` 导入数据库
4. 前端 API 调用时传入新 `symbol` 参数

### Q3: 回测结果是否可靠？
**A**: 
- ⚠️ **数据量有限**：当前仅有 ZEC 的历史数据
- ⚠️ **简单策略**：未考虑滑点、手续费、流动性
- ⚠️ **过拟合风险**：参数可能针对历史数据优化
- ✅ **用于实验与研究**：不应直接用于实盘交易

### Q4: 如何优化策略性能？
**A**: 
1. **增加数据维度**：融合技术指标、链上数据
2. **优化入场/出场逻辑**：动态止损、多条件组合
3. **参数自动优化**：网格搜索、遗传算法
4. **验证集测试**：使用 out-of-sample 数据验证泛化能力

---

## 参考资料

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Lightweight Charts 文档](https://tradingview.github.io/lightweight-charts/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [CryptoPanic API](https://cryptopanic.com/developers/api/)
- [NewsAPI](https://newsapi.org/)

---

**📧 问题反馈**: 请提交 Issue 到 GitHub 仓库  
**📝 贡献指南**: 欢迎 PR！请先阅读 CONTRIBUTING.md（待补充）

**免责声明**: 本系统仅供加密货币市场研究与教育目的，不构成任何投资建议。

---

## Google Trends 通道说明

- Google 通道数据由 `scripts/fetch_multi_symbol_google_trends.py` 批量拉取，支持多币种、**日级分辨率**。
- 关键词配置见 `src/config/attention_channels.py`，如未配置则自动 fallback 为 `["<symbol> crypto"]`。
- 拉取逻辑写入数据库 `google_trends` 表。
- attention 特征工程会自动 merge 真数据，缺失时自动填 0 并记录 warning 日志。

### 📊 每日数据保证

**重要**: 系统已实现智能分段拉取，确保无论时间跨度多长都能获得**每日粒度数据**：

```bash
# ✓ 获取1年每日数据（自动分段拉取，~2-4个请求）
python scripts/fetch_multi_symbol_google_trends.py --days 365 --force-refresh

# ✓ 获取3个月每日数据（单次请求，更快）
python scripts/fetch_multi_symbol_google_trends.py --days 90
```

**技术说明**:
- Google Trends API 限制: ≤269天返回每日数据，>269天返回每周数据
- 系统自动检测时间跨度，>269天时会分段拉取并智能合并
- 详细文档见 `GOOGLE_TRENDS_DAILY_DATA.md`

### 故障处理

- ⚠️ 若 pytrends 未安装或网络异常，Google 通道自动降级为 0，不影响主流程。
- 检查数据质量: `python scripts/test_google_trends_resolution.py`

---

## Attention Regime 研究接口

- 新增 `/api/research/attention-regimes` POST 接口，支持多币种 attention regime 研究。
- 用法示例：
  ```http
  POST /api/research/attention-regimes
  {
    "symbols": ["ZEC", "BTC", "ETH"],
    "lookahead_days": [7, 30],
    "attention_source": "composite",  // 或 "news_channel"
    "split_method": "quantile",
    "start": "2023-01-01",
    "end": "2025-11-01"
  }
  ```
- 返回每个 symbol 在不同 attention regime（如 low/mid/high）下未来收益、波动、正收益比例、最大回撤等统计。
- regime 分段支持分位数（默认 tercile）或中位数。
- 适合 Notebook/脚本批量分析，不直接用于交易信号。
- 推荐用 `scripts/demo_attention_regime_analysis.py` 验证多币种 regime 统计。

---

## Attention Regime 分析方法论

### 1. 核心概念
Attention Regime（注意力体制）分析旨在研究**不同注意力热度区间**对未来价格表现的统计显著性影响。例如：
- 当注意力处于 "High" 区间时，未来 7 天是否倾向于上涨？
- 当注意力处于 "Low" 区间时，市场是否缺乏波动？

### 2. 计算逻辑
后端模块：`src/research/attention_regimes.py`

#### 步骤一：数据对齐
将日级 `attention_score`（或 `composite_attention_score`）与收盘价 `close` 按日期对齐。

#### 步骤二：Regime 划分
根据历史数据的分位数将注意力划分为不同的 Regime：
- **Tercile (三等分)**: Low (0-33%), Mid (33-66%), High (66-100%)
- **Quartile (四等分)**: Q1, Q2, Q3, Q4

#### 步骤三：前瞻收益计算 (Lookahead Return)
对于每个时间点 $t$，计算未来 $k$ 天的对数收益率：
$$ r_{t,k} = \ln(\frac{P_{t+k}}{P_t}) $$

#### 步骤四：统计聚合
按 Regime 分组，统计每个组内的：
- **Avg Return**: 平均收益率
- **Pos Ratio**: 正收益比例（胜率）
- **Sample Count**: 样本数量

### 3. 前端交互
面板位置：Dashboard 底部 "Attention Regime Analysis"

**输入参数**：
- **Symbols**: 逗号分隔的币种列表（如 `ZEC,BTC,ETH`）
- **Lookahead Days**: 逗号分隔的天数（如 `7,30`）
- **Attention Source**: `composite` (合成) 或 `news_channel` (仅新闻)
- **Split Method**: `tercile` (三等分) 或 `quartile` (四等分)

**输出解读**：
表格展示了每个 Symbol 在不同 Regime 下的表现。
- 如果 **High Regime** 的 **Avg Return** 显著高于 **Low Regime**，说明高注意力可能预示着价格上涨（动量效应）。
- 如果 **High Regime** 的 **Avg Return** 为负，可能暗示过度关注后的反转（Reversal）。

---

## State Snapshot（状态快照）🆕

State Snapshot 模块用于构建某个 symbol 在特定时刻的**多维状态特征向量**，整合价格、波动率、注意力等多个维度的信息。状态快照是 **Scenario Engine** 的核心输入，可用于：

- **相似模式检索**：找到历史上与当前状态相似的时刻
- **情景分析**：研究类似状态下的后续价格表现
- **多因子综合评估**：一站式获取 symbol 当前的市场状态

### 概念说明

状态快照将 symbol 在某时刻的多维信息压缩为一个标准化的特征向量（`features`）和原始统计值（`raw_stats`）：

- **features**：所有特征经过 z-score 或等效标准化处理，量纲统一，适合用于相似度计算和机器学习模型输入
- **raw_stats**：保留原始数值（如收盘价、成交量等），便于前端展示和调试

### 特征列表

| 维度 | 特征名 | 含义 | 计算方式 |
|------|--------|------|----------|
| **价格/波动** | `ret_window` | 窗口累计对数收益的 z-score | 相对于历史滚动窗口收益分布 |
| | `vol_window` | 窗口波动率的 z-score | 相对于历史滚动窗口波动率分布 |
| | `volume_zscore` | 近 7D 平均成交量的 z-score | 相对于窗口内成交量分布 |
| **Attention** | `att_composite_z` | 合成注意力 z-score | 直接使用 `composite_attention_zscore` |
| | `att_news_z` | 新闻通道 z-score | 直接使用 `news_channel_score` |
| | `att_trend_7d` | 近 7D 注意力趋势斜率 | 线性回归斜率，标准化后 |
| | `att_spike_flag` | 注意力 spike 标志 | 0/1，来自 `composite_attention_spike_flag` |
| **通道结构** | `att_news_share` | 新闻通道在合成中的占比 | 基于各通道 z-score 绝对值估算 |
| | `att_google_share` | Google Trends 通道占比 | 同上 |
| | `att_twitter_share` | Twitter 通道占比 | 同上 |
| **情绪** | `sentiment_mean_window` | 窗口内平均情绪分数 | 从新闻 sentiment_score 聚合 |
| | `bullish_minus_bearish` | 多空情绪差值的 z-score | bullish_attention - bearish_attention |

### 原始统计 (raw_stats)

| 字段 | 含义 |
|------|------|
| `close_price` | 最新收盘价 |
| `high_window` / `low_window` | 窗口内最高/最低价 |
| `avg_volume_7d` / `avg_volume_window` | 近 7D / 窗口内平均成交量 |
| `return_window_pct` | 窗口累计收益率（百分比形式） |
| `volatility_window` | 窗口波动率原始值 |
| `composite_attention_score` | 最新合成注意力分数 |
| `google_trend_value` / `twitter_volume` | 最新 Google/Twitter 通道值 |
| `news_count_7d` / `news_count_window` | 近 7D / 窗口内新闻数量 |
| `avg_bullish` / `avg_bearish` | 窗口内平均多/空注意力 |
| `avg_composite_score` | 窗口内平均合成分数 |
| `sentiment_mean_window` | 窗口内平均情绪分数（原始值） |

### API 使用

#### 获取单个 symbol 状态快照

```http
GET /api/state/snapshot?symbol=ZEC&timeframe=1d&window_days=30
```

**参数说明**：
- `symbol`（必填）：币种符号，如 `ZEC`, `BTC`
- `timeframe`（可选）：时间粒度，`1d`（日级，默认）或 `4h`
- `window_days`（可选）：特征计算窗口天数，7-365，默认 30

**响应示例**：
```json
{
  "symbol": "ZEC",
  "as_of": "2025-11-29T12:00:00+00:00",
  "timeframe": "1d",
  "window_days": 30,
  "features": {
    "ret_window": 0.52,
    "vol_window": -0.31,
    "volume_zscore": 1.24,
    "att_composite_z": 0.87,
    "att_news_z": 0.65,
    "att_trend_7d": 0.12,
    "att_spike_flag": 0,
    "att_news_share": 0.45,
    "att_google_share": 0.35,
    "att_twitter_share": 0.20,
    "sentiment_mean_window": 0.15,
    "bullish_minus_bearish": 0.32
  },
  "raw_stats": {
    "close_price": 45.67,
    "high_window": 52.30,
    "low_window": 38.12,
    "avg_volume_7d": 12345678.0,
    "composite_attention_score": 2.34,
    "news_count_7d": 15
  }
}
```

#### 批量获取多个 symbol 状态快照

```http
POST /api/state/snapshot/batch
Content-Type: application/json

{
  "symbols": ["ZEC", "BTC", "ETH"],
  "timeframe": "1d",
  "window_days": 30
}
```

**响应示例**：
```json
{
  "snapshots": {
    "ZEC": { "symbol": "ZEC", "features": {...}, "raw_stats": {...} },
    "BTC": { "symbol": "BTC", "features": {...}, "raw_stats": {...} },
    "ETH": null
  },
  "meta": {
    "requested": 3,
    "success": 2,
    "failed": 1
  }
}
```

### Python 使用示例

```python
from src.research.state_snapshot import compute_state_snapshot, compute_state_snapshots_batch
from datetime import datetime, timezone

# 获取单个 symbol 的当前状态
snapshot = compute_state_snapshot("ZEC")
if snapshot:
    print(f"Symbol: {snapshot.symbol}")
    print(f"Features: {snapshot.features}")
    print(f"Close Price: {snapshot.raw_stats.get('close_price')}")

# 指定历史时间点
as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
snapshot = compute_state_snapshot("BTC", as_of=as_of, window_days=60)

# 批量计算
snapshots = compute_state_snapshots_batch(
    symbols=["ZEC", "BTC", "ETH"],
    timeframe="1d",
    window_days=30
)
for symbol, snap in snapshots.items():
    if snap:
        print(f"{symbol}: att_composite_z = {snap.features.get('att_composite_z', 0):.2f}")
```

### 用途：作为 Scenario Engine 的输入

State Snapshot 是 Scenario Engine（情景分析引擎）的核心输入。典型工作流：

1. **当前状态捕捉**：调用 `compute_state_snapshot(symbol)` 获取当前市场状态
2. **历史相似模式检索**：计算当前 `features` 向量与历史所有时刻的相似度（如余弦相似度、欧氏距离）
3. **情景分析**：找到 Top-K 相似的历史时刻，统计这些时刻之后的价格表现
4. **决策支持**：基于历史相似模式的表现分布，评估当前状态的潜在风险和机会

### 设计理念与扩展方向

**当前版本（v1）**：Rule-based 特征工程
- 手工设计的价格、波动、注意力等特征
- z-score 标准化确保量纲统一
- 适合快速验证和解释性分析

**未来扩展方向**：
- **ML Embedding**：使用 Autoencoder / Transformer 学习更丰富的状态表示
- **动态权重**：根据市场环境自适应调整各特征的重要性
- **多时间尺度**：融合短周期（4h）和长周期（1d/1w）的状态信息
- **跨币种状态**：同时考虑多个 symbol 的市场状态（如 BTC 主导性）

---

## 相似状态检索（Similar States）🆕

相似状态检索是 Scenario Engine 的第二步，用于在历史数据中查找与当前市场状态相似的时刻。这是一种**基于特征空间的 KNN（K-Nearest Neighbors）近似方法**，主要用于情景分析和研究，而非高频交易模型。

### 核心概念

**基本思路**：
1. 将 StateSnapshot 的 `features` 向量视为高维空间中的一个点
2. 计算目标点与所有历史点的距离
3. 返回距离最近的 Top-K 个历史样本

**应用场景**：
- **情景分析**：当前市场状态与历史上哪些时刻相似？那些时刻之后发生了什么？
- **风险评估**：历史相似状态的后续表现分布如何？最差情况是什么？
- **机会发现**：历史上类似状态后出现大幅上涨的概率是多少？

### 实现细节

**模块位置**：`src/research/similar_states.py`

**核心数据结构**：

```python
@dataclass
class SimilarState:
    symbol: str           # 币种符号
    datetime: datetime    # 历史时间点
    timeframe: str        # 时间粒度
    distance: float       # 特征空间距离（越小越相似）
    similarity: float     # 相似度分数 (0-1)
    snapshot_summary: Dict[str, Any]  # 关键统计摘要
    features: Dict[str, float]        # 完整特征向量
```

**距离计算**：

当前支持两种距离度量：

| 度量方式 | 公式 | 特点 |
|---------|------|------|
| 欧氏距离 | $d = \sqrt{\sum_i (x_i - y_i)^2}$ | 考虑特征的绝对差异，对量级敏感 |
| 余弦距离 | $d = 1 - \frac{x \cdot y}{\|x\| \|y\|}$ | 考虑特征的方向相似性，忽略量级 |

默认使用**欧氏距离**，因为 StateSnapshot 的特征已经过 z-score 标准化。

**防止信息泄露**：
- 自动排除目标时间点 ±7 天内的历史样本
- 可选择是否包含相同 symbol 的历史状态

### API 使用

#### 基础查询

```http
GET /api/state/similar-cases?symbol=ZEC&timeframe=1d&window_days=30&top_k=50
```

**参数说明**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `symbol` | string | 必填 | 目标币种 |
| `timeframe` | string | "1d" | 时间粒度 |
| `window_days` | int | 30 | 特征计算窗口 |
| `top_k` | int | 50 | 返回样本数量 |
| `max_history_days` | int | 365 | 最大回溯天数 |
| `include_same_symbol` | bool | true | 是否包含相同币种 |

**响应示例**：
```json
{
  "target": {
    "symbol": "ZEC",
    "as_of": "2025-11-29T12:00:00+00:00",
    "features": {"ret_window": 0.52, "att_composite_z": 0.87, ...},
    "raw_stats": {"close_price": 45.67, ...}
  },
  "similar_cases": [
    {
      "symbol": "ZEC",
      "datetime": "2024-06-15T00:00:00+00:00",
      "timeframe": "1d",
      "distance": 1.234,
      "similarity": 0.85,
      "snapshot_summary": {
        "close_price": 42.50,
        "return_window_pct": 0.12,
        "composite_attention_score": 2.1,
        ...
      }
    },
    ...
  ],
  "meta": {
    "total_candidates_processed": 1095,
    "results_returned": 50,
    "message": "Found 50 similar historical states"
  }
}
```

#### 高级查询（自定义参数）

```http
POST /api/state/similar-cases/custom
Content-Type: application/json

{
  "symbol": "ZEC",
  "timeframe": "1d",
  "window_days": 30,
  "top_k": 100,
  "max_history_days": 730,
  "candidate_symbols": ["ZEC", "BTC", "ETH"],
  "distance_metric": "cosine",
  "include_same_symbol": true,
  "exclusion_days": 14
}
```

### Python 使用示例

```python
from src.research.similar_states import find_similar_states, find_similar_states_for_symbol
from src.research.state_snapshot import compute_state_snapshot

# 方式一：便捷函数
target, similar_states = find_similar_states_for_symbol(
    symbol="ZEC",
    timeframe="1d",
    window_days=30,
    top_k=20,
    max_history_days=180,
    verbose=True,
)

# 查看结果
for state in similar_states[:5]:
    print(f"{state.symbol} @ {state.datetime.strftime('%Y-%m-%d')}")
    print(f"  Distance: {state.distance:.4f}, Similarity: {state.similarity:.2%}")
    print(f"  Close: ${state.snapshot_summary['close_price']:.2f}")

# 方式二：完整控制
target = compute_state_snapshot("ZEC")
similar_states = find_similar_states(
    target=target,
    candidate_symbols=["ZEC", "BTC", "ETH"],
    timeframe="1d",
    window_days=30,
    top_k=50,
    distance_metric="euclidean",
)
```

### 遍历历史状态

```python
from src.research.similar_states import iter_historical_states

# 遍历多个币种的历史状态
for snapshot in iter_historical_states(
    symbols=["ZEC", "BTC"],
    timeframe="1d",
    window_days=30,
    max_history_days=90,
    verbose=True,
):
    print(f"{snapshot.symbol} @ {snapshot.as_of}: "
          f"att_z={snapshot.features.get('att_composite_z', 0):.2f}")
```

### 性能注意事项

**当前实现**：在线计算（实时遍历历史数据）
- 适合研究和中等规模数据（< 3 年历史，< 10 个币种）
- 典型查询时间：5-30 秒（取决于数据量）

**优化建议**：
- 限制 `max_history_days` 和候选币种数量
- 对于高频使用场景，考虑预计算特征缓存
- 未来可扩展为向量数据库方案（如 Milvus、Faiss）

### 结果解读

**距离（distance）**：
- 值越小表示越相似
- 欧氏距离通常在 0-10 范围内
- 余弦距离范围为 [0, 2]

**相似度（similarity）**：
- 值越大表示越相似，范围 (0, 1]
- 基于指数衰减计算：$similarity = e^{-distance / scale}$

**使用建议**：
1. 先查看 Top-10 结果，评估相似度是否合理
2. 检查相似样本的时间分布，避免集中在某一时段
3. 结合 `snapshot_summary` 理解相似点的具体市场状态
4. 分析相似样本后续的价格表现（需要额外查询价格数据）

---

## Attention Scenario Engine（情景分析引擎）

基于 Attention + Price 的状态特征与历史相似状态，构建多情景未来走势分析系统。

### 核心思想

Scenario Engine 的核心逻辑：
1. **状态表示**：将当前市场状态编码为多维特征向量（StateSnapshot）
2. **相似检索**：在历史数据中查找与当前状态相似的时刻（Similar States）
3. **情景分析**：分析这些相似样本的后续价格表现，归纳出多种可能情景

### 情景分类

当前实现为 **rule-based** 分类，后续可替换为 ML/聚类方法：

| 情景标签 | 英文 | 分类规则 | 描述 |
|---------|------|---------|------|
| 持续上涨 | `trend_up` | 7D 收益 > 5% 且回撤 > -5% | 价格持续走高，回撤可控 |
| 持续下跌 | `trend_down` | 7D 收益 < -5% | 价格持续走低 |
| 冲高回落 | `spike_and_revert` | 3D 收益 > 3% 且 7D 收益 < 2% | 短期上涨后回吐大部分涨幅 |
| 急剧下跌 | `crash` | 7D/30D 回撤 < -15% | 出现大幅回撤 |
| 横盘震荡 | `sideways` | 默认情况 | 价格波动有限，方向不明确 |

### 分类阈值配置

分类阈值定义在 `src/research/scenarios.py` 中，可根据数据特性调整：

```python
# 收益率阈值
THRESHOLD_TREND_UP = 0.05       # 7D 收益 > 5% 视为上涨趋势
THRESHOLD_TREND_DOWN = -0.05   # 7D 收益 < -5% 视为下跌趋势
THRESHOLD_SPIKE = 0.03          # 3D 收益 > 3% 视为短期冲高
THRESHOLD_SMALL = 0.02          # |收益| < 2% 视为横盘/微小波动

# 最大回撤阈值
THRESHOLD_DD_SMALL = -0.05      # 回撤 > -5% 视为小幅回撤
THRESHOLD_DD_LARGE = -0.15      # 回撤 < -15% 视为大幅回撤
```

### API 端点

#### GET `/api/state/scenarios`

对当前 symbol 进行情景分析。

**参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `symbol` | string | 必填 | 目标币种，如 ZEC, BTC |
| `timeframe` | string | "1d" | 时间粒度：1d 或 4h |
| `window_days` | int | 30 | 特征计算窗口 |
| `top_k` | int | 100 | 用于分析的相似样本数量 |
| `max_history_days` | int | 365 | 最大历史回溯天数 |
| `include_sample_details` | bool | false | 是否包含样本详情 |

**请求示例**：
```http
GET /api/state/scenarios?symbol=ZEC&timeframe=1d&top_k=100
```

**响应示例**：
```json
{
  "target": {
    "symbol": "ZEC",
    "as_of": "2025-11-29T12:00:00+00:00",
    "features": {"ret_window": 0.52, "att_composite_z": 0.87, ...},
    "raw_stats": {"close_price": 45.67, ...}
  },
  "scenarios": [
    {
      "label": "sideways",
      "description": "横盘震荡：价格波动有限，方向不明确，适合区间操作或观望",
      "sample_count": 45,
      "probability": 0.45,
      "avg_return_3d": 0.005,
      "avg_return_7d": 0.012,
      "avg_return_30d": 0.025,
      "max_drawdown_7d": -0.03,
      "max_drawdown_30d": -0.08,
      "avg_path": [0, 0.01, 0.02, ...]
    },
    {
      "label": "trend_up",
      "description": "持续上涨：价格在观察期内持续走高，回撤可控，适合趋势跟踪策略",
      "sample_count": 25,
      "probability": 0.25,
      "avg_return_3d": 0.02,
      "avg_return_7d": 0.08,
      "avg_return_30d": 0.15,
      "max_drawdown_7d": -0.02,
      "max_drawdown_30d": -0.06
    },
    ...
  ],
  "meta": {
    "total_similar_samples": 100,
    "valid_samples_analyzed": 85,
    "lookahead_days": [3, 7, 30],
    "message": "Scenario analysis complete: 5 scenarios identified"
  }
}
```

#### POST `/api/state/scenarios/custom`

自定义参数的情景分析（高级用法）。

**请求示例**：
```http
POST /api/state/scenarios/custom
Content-Type: application/json

{
  "symbol": "ZEC",
  "timeframe": "1d",
  "window_days": 30,
  "top_k": 150,
  "max_history_days": 730,
  "lookahead_days": [3, 7, 14, 30, 60],
  "candidate_symbols": ["ZEC", "BTC", "ETH"],
  "include_sample_details": true
}
```

### Python 使用示例

```python
from src.research.scenarios import (
    analyze_scenarios,
    analyze_scenarios_for_symbol,
)
from src.research.state_snapshot import compute_state_snapshot
from src.research.similar_states import find_similar_states

# 方式一：便捷函数
target, scenarios = analyze_scenarios_for_symbol(
    symbol="ZEC",
    timeframe="1d",
    window_days=30,
    top_k=100,
    max_history_days=365,
    lookahead_days=[3, 7, 30],
    include_sample_details=False,
)

# 查看结果
for s in scenarios:
    print(f"\n{s.label.upper()}")
    print(f"  概率: {s.probability:.1%} ({s.sample_count} 样本)")
    print(f"  7D 平均收益: {s.avg_return_7d:.2%}")
    print(f"  7D 平均回撤: {s.max_drawdown_7d:.2%}")

# 方式二：完整控制
target = compute_state_snapshot("ZEC")
similar_states = find_similar_states(target, top_k=100)
scenarios = analyze_scenarios(
    target=target,
    similar_states=similar_states,
    lookahead_days=[3, 7, 30],
)
```

### ScenarioSummary 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `label` | string | 情景标签 |
| `description` | string | 人类可读描述 |
| `sample_count` | int | 样本数量 |
| `probability` | float | 相对概率 (0-1) |
| `avg_return_3d` | float | 3 日平均收益 |
| `avg_return_7d` | float | 7 日平均收益 |
| `avg_return_30d` | float | 30 日平均收益 |
| `max_drawdown_7d` | float | 7 日平均最大回撤 |
| `max_drawdown_30d` | float | 30 日平均最大回撤 |
| `avg_path` | List[float] | 平均价格路径（相对起点） |
| `sample_details` | List[Dict] | 样本详情（可选） |

### 结果解读

**概率（probability）**：
- 表示该情景在相似历史样本中的占比
- 例如 `probability=0.45` 表示 45% 的相似样本属于该情景
- 注意：这是历史统计概率，不代表未来一定会发生

**平均收益（avg_return）**：
- 使用对数收益率计算
- 正值表示上涨，负值表示下跌
- 例如 `avg_return_7d=0.08` 表示 7 天平均上涨约 8%

**最大回撤（max_drawdown）**：
- 负数表示，例如 `-0.15` 表示 15% 回撤
- 反映该情景下的潜在风险

**平均路径（avg_path）**：
- 相对起点的标准化价格轨迹
- 可用于可视化典型走势
- 例如 `[0, 0.01, 0.02, 0.015, ...]` 表示第 1 天涨 1%，第 2 天涨 2%...

### ⚠️ 重要声明

1. **研究工具**：本情景分析系统为研究和趋势推演工具，**不构成交易建议**
2. **历史局限**：过往表现不代表未来收益，市场条件可能发生根本性变化
3. **样本量**：结论可靠性取决于样本量，建议 `top_k >= 50` 以获得统计意义
4. **规则分类**：当前为 rule-based 实现，后续可升级为 ML/聚类方法以提升精度

### 未来扩展方向

1. **ML 分类模型**：使用 K-means 或 DBSCAN 聚类替代规则分类
2. **时间衰减权重**：近期样本给予更高权重
3. **相似度加权**：按相似度加权计算平均收益
4. **置信区间**：添加收益分布的置信区间
5. **情景可视化**：前端展示各情景的平均路径图表

---
