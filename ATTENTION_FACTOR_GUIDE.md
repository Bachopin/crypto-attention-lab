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

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      数据采集层                              │
│  CryptoPanic | NewsAPI | CryptoCompare | RSS Feeds         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   特征工程层                                 │
│  news_features.py: source_weight, sentiment, tags           │
│  attention_features.py: weighted/bullish/bearish/intensity  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  事件检测 & 策略层                           │
│  attention_events.py: 分位数阈值事件检测                     │
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

位置：`src/features/attention_features.py`

从新闻级特征聚合为日级：
```python
attention_score = min_max_normalize(news_count, 0-100)
weighted_attention = sum(source_weight * relevance_weight)
bullish_attention = sum(positive_sentiment * weighted)
bearish_attention = sum(negative_sentiment * weighted)
event_intensity = has_high_weight_source AND strong_sentiment AND has_tags ? 1 : 0
```

保存到 `data/processed/attention_features_zec.csv` 和数据库。

### 4. 事件检测
位置：`src/events/attention_events.py`

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

### 来源权重表
```python
SOURCE_WEIGHTS = {
    "CoinDesk": 1.0,         # 顶级主流媒体
    "Cointelegraph": 0.9,    # 主流加密媒体
    "CryptoPanic": 0.8,      # 聚合平台
    "CryptoCompare": 0.7,    # 数据平台
    "CryptoSlate": 0.6,      # 垂直媒体
    "RSS": 0.5,              # RSS 聚合
    "Unknown": 0.4,          # 未知来源
}
```

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
