# FastAPI Backend Documentation

## 📋 Overview

本文档描述了 Crypto Attention Lab 的 FastAPI 后端 API 接口规范。

**Base URL:** `http://localhost:8000`  
**API Docs:** `http://localhost:8000/docs` (Swagger UI)  
**ReDoc:** `http://localhost:8000/redoc` (Alternative API docs)

---

## 🔌 API Endpoints

### 1. Health Check

#### `GET /health`

检查 API 服务健康状态。

**Response:**
```json
{
  "status": "healthy"
}
```

---

#### `GET /ping`

简单的 ping 端点。

**Response:**
```json
{
  "message": "pong"
}
```

---

### 2. Price Data

#### `GET /api/price`

获取 OHLCV 价格数据。

**Query Parameters:**

|-------------|--------|----------|----------|--------------------------------|
| `symbol`    | string | No       | ZECUSDT  | 交易对符号 (e.g., ZECUSDT)     |
| `start`     | string | No       | -        | 开始时间 (ISO 8601 格式)       |
| `end`       | string | No       | -        | 结束时间 (ISO 8601 格式)       |

**Example Request:**
```bash
curl "http://localhost:8000/api/price?symbol=ZECUSDT&timeframe=1d&start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z"
```

**Response:**
```json
[
  {
    "timestamp": 1704067200000,
    "datetime": "2024-01-01T00:00:00Z",
    "open": 45.23,
    "high": 46.78,
    "low": 44.91,
    "close": 46.12,
    "volume": 123456.78
  },
  {
    "timestamp": 1704153600000,
    "datetime": "2024-01-02T00:00:00Z",
    "open": 46.12,
    "high": 47.50,
    "low": 45.80,
    "close": 47.01,
    "volume": 156789.12
  }
]
```

**Response Fields:**

| Field      | Type   | Description                           |
|------------|--------|---------------------------------------|
| `timestamp`| number | Unix timestamp in milliseconds        |
| `datetime` | string | ISO 8601 datetime string              |
| `open`     | number | Opening price                         |
| `high`     | number | Highest price                         |
| `low`      | number | Lowest price                          |
| `close`    | number | Closing price                         |
| `volume`   | number | Trading volume                        |

---

### 3. Attention Data

#### `GET /api/attention`

获取注意力分数时间序列数据。

**Query Parameters:**

| Parameter     | Type   | Required | Default | Description                    |
|---------------|--------|----------|---------|--------------------------------|
| `symbol`      | string | No       | ZEC     | 币种符号 (e.g., ZEC, BTC)      |
| `granularity` | string | No       | 1d      | 数据粒度 (目前仅支持 1d)       |
| `start`       | string | No       | -       | 开始时间 (ISO 8601 格式)       |
| `end`         | string | No       | -       | 结束时间 (ISO 8601 格式)       |

**Example Request:**
```bash
curl "http://localhost:8000/api/attention?symbol=ZEC&granularity=1d&start=2024-01-01T00:00:00Z"
```

**Response:**
```json
[
  {
    "timestamp": 1704067200000,
    "datetime": "2024-01-01T00:00:00Z",
    "attention_score": 67.5,
    "news_count": 12
  },
  {
    "timestamp": 1704153600000,
    "datetime": "2024-01-02T00:00:00Z",
    "attention_score": 72.3,
    "news_count": 15
  }
]
```

**Response Fields:**

| Field              | Type   | Description                        |
|--------------------|--------|------------------------------------|
| `timestamp`        | number | Unix timestamp in milliseconds     |
| `datetime`         | string | ISO 8601 datetime string           |
| `attention_score`  | number | Attention score (0-100)            |
| `news_count`       | number | Number of news articles            |

---

### 4. News Data

#### `GET /api/news`

获取新闻数据。

**Query Parameters:**

| Parameter | Type   | Required | Default | Description                    |
|-----------|--------|----------|---------|--------------------------------|
| `symbol`  | string | No       | ZEC     | 币种符号 (e.g., ZEC, BTC)      |
| `start`   | string | No       | -       | 开始时间 (ISO 8601 格式)       |
| `end`     | string | No       | -       | 结束时间 (ISO 8601 格式)       |

**Example Request:**
```bash
curl "http://localhost:8000/api/news?symbol=ZEC&start=2024-01-01T00:00:00Z&end=2024-01-31T23:59:59Z"
```

**Response:**
```json
[
  {
    "datetime": "2024-01-01T10:30:00Z",
    "source": "CryptoPanic",
    "title": "ZEC Price Surges on Privacy Upgrade Announcement",
    "url": "https://cryptopanic.com/news/..."
  },
  {
    "datetime": "2024-01-01T14:15:00Z",
    "source": "NewsAPI",
    "title": "Zcash Foundation Releases Q4 Development Update",
    "url": "https://newsapi.org/v2/..."
  }
]
```

**Response Fields:**

| Field      | Type   | Description                        |
|------------|--------|------------------------------------|
| `datetime` | string | ISO 8601 datetime string           |
| `source`   | string | News source (CryptoPanic, NewsAPI) |
| `title`    | string | News headline                      |
| `url`      | string | Link to full article               |

---

### 5. Attention Events

#### `GET /api/attention-events`

获取注意力事件列表（如关注度飙升、情绪异常等）。

**Query Parameters:**

| Parameter       | Type   | Required | Default | Description                    |
|-----------------|--------|----------|---------|--------------------------------|
| `symbol`        | string | No       | ZEC     | 币种符号                       |
| `start`         | string | No       | -       | 开始时间 (ISO 8601)            |
| `end`           | string | No       | -       | 结束时间 (ISO 8601)            |
| `lookback_days` | int    | No       | 30      | 计算基准的回溯天数             |
| `min_quantile`  | float  | No       | 0.8     | 触发事件的分位数阈值 (0-1)     |

**Example Request:**
```bash
curl "http://localhost:8000/api/attention-events?symbol=ZEC&lookback_days=30&min_quantile=0.9"
```

**Response:**
```json
[
  {
    "datetime": "2024-01-15T00:00:00Z",
    "event_type": "attention_spike",
    "intensity": 25.5,
    "summary": "news_count=10, att=85.0, w_att=42.5"
  },
  {
    "datetime": "2024-01-20T00:00:00Z",
    "event_type": "high_bullish",
    "intensity": 15.0,
    "summary": "news_count=8, att=60.0, w_att=30.0"
  }
]
```

---

### 6. Backtest

#### `POST /api/backtest/basic-attention`

运行基础注意力策略回测，支持简单风控参数。

**Request Body:**

```json
{
  "symbol": "ZECUSDT",
  "lookback_days": 30,
  "attention_quantile": 0.8,
  "max_daily_return": 0.05,
  "holding_days": 3,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.1,
  "max_holding_days": 5,
  "position_size": 1.0,
  "attention_source": "legacy",
  "start": "2024-01-01T00:00:00Z",
  "end": "2024-12-31T23:59:59Z"
}
```

可选字段 `attention_condition` 支持使用注意力 Regime 驱动信号（策略 Preset 功能）：

```json
{
  "attention_condition": {
    "source": "news_channel",
    "regime": "high",
    "lookback_days": 45
  }
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `source` | string | ✅ | - | 注意力通道：`composite`（多通道融合）或 `news_channel`（新闻通道） |
| `regime` | string | ✅ | - | 分位档位：`low`（0-33%）、`mid`（33-67%）、`high`（67-100%）或 `custom` |
| `lower_quantile` | float | ❌ | - | 仅 `regime="custom"` 时有效，下限分位（0-1） |
| `upper_quantile` | float | ❌ | - | 仅 `regime="custom"` 时有效，上限分位（0-1） |
| `lookback_days` | int | ❌ | 30 | 计算 rolling quantile 的回溯窗口天数 |

**Regime 档位映射：**
- `low`: lower_quantile=0.0, upper_quantile=0.33
- `mid`: lower_quantile=0.33, upper_quantile=0.67  
- `high`: lower_quantile=0.67, upper_quantile=1.0
- `custom`: 需手动提供 lower_quantile 与 upper_quantile

**策略 Preset 示例（前端可保存并复用）：**

```json
{
  "attention_condition": {
    "source": "composite",
    "regime": "custom",
    "lower_quantile": 0.7,
    "upper_quantile": 0.9,
    "lookback_days": 60
  }
}
```

当提供 `attention_condition` 时，API 会使用 `build_attention_signal_series()` 生成 0/1 入场信号，替代原有的 `attention_quantile` 逻辑。响应的 `summary.attention_condition` 与 `meta.attention_condition` 中会包含使用的条件详情。

**可选字段 `attention_source`:**
- `"legacy"`（默认）使用历史 `weighted_attention` 逻辑；
- `"composite"` 使用多通道融合后的 `composite_attention_score`。
若指定的通道缺少所需字段，API 会返回错误提示。

**Response:**
```json
{
  "summary": {
    "total_trades": 5,
    "win_rate": 60.0,
    "avg_return": 0.045,
    "cumulative_return": 0.24,
    "max_drawdown": 0.10,
    "max_consecutive_losses": 2,
    "monthly_returns": {
      "2024-01": 0.12,
      "2024-02": 0.03
    },
    "attention_condition": {
      "source": "news_channel",
      "regime": "high",
      "lower_quantile": null,
      "upper_quantile": null,
      "lookback_days": 45
    }
  },
  "trades": [
    {
      "entry_date": "2024-01-15T00:00:00Z",
      "exit_date": "2024-01-18T00:00:00Z",
      "entry_price": 50.0,
      "exit_price": 55.0,
      "return_pct": 0.10
    }
  ],
  "equity_curve": [
    { "datetime": "2024-01-18T00:00:00Z", "equity": 1.10 }
  ]
}
```

#### `POST /api/backtest/basic-attention/multi`

运行多币种基础注意力策略回测，对比不同币种的策略表现。

**Request Body:**

```json
{
  "symbols": ["ZECUSDT", "BTCUSDT", "ETHUSDT"],
  "lookback_days": 30,
  "attention_quantile": 0.8,
  "max_daily_return": 0.05,
  "holding_days": 3,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.1,
  "max_holding_days": 5,
  "position_size": 1.0,
  "attention_source": "composite",
  "start": "2024-01-01T00:00:00Z",
  "end": "2024-12-31T23:59:59Z"
}
```

与单币端点一致，`attention_source` 支持 `legacy` / `composite`，默认 `legacy`。响应会在 `meta.attention_source` 中注明本次使用的通道。

**Response:**

```json
{
  "per_symbol_summary": {
    "ZECUSDT": {
      "total_trades": 5,
      "win_rate": 60.0,
      "avg_return": 0.045,
      "cumulative_return": 0.24,
      "max_drawdown": 0.10
    },
    "BTCUSDT": {
      "total_trades": 3,
      "win_rate": 66.7,
      "avg_return": 0.03,
      "cumulative_return": 0.09,
      "max_drawdown": 0.05
    }
  },
  "per_symbol_equity_curves": {
    "ZECUSDT": [
      { "datetime": "2024-01-18T00:00:00Z", "equity": 1.10 }
    ],
    "BTCUSDT": [
      { "datetime": "2024-02-10T00:00:00Z", "equity": 1.05 }
    ]
  },
  "meta": {
    "attention_source": "composite",
    "symbols": ["ZECUSDT", "BTCUSDT", "ETHUSDT"]
  },
  "per_symbol_meta": {
    "ZECUSDT": {
      "attention_source": "composite",
      "signal_field": "composite_attention_score"
    }
  }
}
```

`attention_condition` 同样适用于多币端点，所有币种共用同一条件。例如：

```json
{
  "attention_condition": {
    "source": "composite",
    "regime": "custom",
    "lower_quantile": 0.2,
    "upper_quantile": 0.8,
    "lookback_days": 60
  }
}
```

响应的 `per_symbol_summary.*.attention_condition` 与单币接口一致，便于在前端显示策略 Preset。若未提供该字段，则沿用原有分位阈值逻辑。

**多币对比示例响应：**

```json
{
  "per_symbol_summary": {
    "ZECUSDT": {
      "total_trades": 5,
      "win_rate": 60.0,
      "attention_condition": {
        "source": "composite",
        "regime": "custom",
        "lower_quantile": 0.2,
        "upper_quantile": 0.8,
        "lookback_days": 60
      }
    }
  }
}
```

`meta` 区域记录了本次批量回测共享的 attention 来源，`per_symbol_meta` 用于排查单个标的的信号字段（例如个别币种缺少 composite 数据时快速定位）。

---

### 7. Attention Event Performance

#### `GET /api/attention-events/performance`

按事件类型统计事件后的平均收益表现，用于分析事件与收益的关联。

**Query Parameters:**

| Parameter       | Type   | Required | Default | Description                              |
|-----------------|--------|----------|---------|------------------------------------------|
| `symbol`        | string | No       | ZEC     | 币种符号（例如 ZEC、BTC）                 |
| `lookahead`     | string | No       | 1,3,5,10| 逗号分隔的前瞻天数列表，如 `1,3,5,10`    |

**Example Request:**

```bash
curl "http://localhost:8000/api/attention-events/performance?symbol=ZEC&lookahead=1,3,5,10"
```

**Response:**

```json
{
  "high_weighted_event": {
    "1": { "avg_return": 0.012, "sample_size": 10 },
    "3": { "avg_return": 0.025, "sample_size": 10 },
    "5": { "avg_return": 0.031, "sample_size": 9 }
  },
  "high_bullish": {
    "1": { "avg_return": 0.008, "sample_size": 7 },
    "3": { "avg_return": 0.020, "sample_size": 7 }
  }
}
```

---

### 8. Attention Rotation Backtest

#### `POST /api/backtest/attention-rotation`

运行多币种 Attention 轮动策略回测。

**Request Body:**

```json
{
  "symbols": ["ZECUSDT", "BTCUSDT", "ETHUSDT"],
  "attention_source": "composite",
  "rebalance_days": 7,
  "lookback_days": 30,
  "top_k": 2,
  "start": "2024-01-01T00:00:00Z",
  "end": "2024-12-31T23:59:59Z"
}
```

**Response:**

```json
{
  "params": {
    "symbols": ["ZECUSDT", "BTCUSDT", "ETHUSDT"],
    "attention_source": "composite",
    "rebalance_days": 7,
    "lookback_days": 30,
    "top_k": 2,
    "start": "2024-01-01T00:00:00+00:00",
    "end": "2024-12-31T23:59:59+00:00"
  },
  "equity_curve": [
    {"datetime": "2024-01-01T00:00:00+00:00", "equity": 1.0},
    {"datetime": "2024-01-02T00:00:00+00:00", "equity": 1.01}
  ],
  "rebalance_log": [
    {
      "rebalance_date": "2024-01-01T00:00:00+00:00",
      "selected_symbols": ["BTCUSDT", "ETHUSDT"],
      "attention_values": {"BTCUSDT": 1.2, "ETHUSDT": 0.9, "ZECUSDT": 0.5}
    }
  ],
  "summary": {
    "total_return": 0.15,
    "annualized_return": 0.15,
    "max_drawdown": 0.05,
    "volatility": 0.2,
    "sharpe": 0.75,
    "num_rebalances": 52,
    "start_date": "2024-01-01T00:00:00+00:00",
    "end_date": "2024-12-31T23:59:59+00:00"
  }
}
```

---

  }
}

---

### 9. Scenario Analysis (Similar States)

#### `GET /api/state/snapshot`

获取当前（或指定日期）的市场状态特征向量。

**Query Parameters:**

| Parameter | Type   | Required | Default | Description                    |
|-----------|--------|----------|---------|--------------------------------|
| `symbol`  | string | No       | ZEC     | 币种符号                       |
| `date`    | string | No       | -       | 指定日期 (ISO 8601)，默认为最新数据 |

**Response:**

```json
{
  "date": "2024-03-20T00:00:00",
  "price": 150.5,
  "features": {
    "trend_7d": 0.05,
    "volatility_30d": 0.02,
    "attention_score": 75.0,
    "rel_volume": 1.2
  }
}
```

#### `GET /api/state/similar-cases`

查找历史相似状态。

**Query Parameters:**

| Parameter | Type   | Required | Default | Description                    |
|-----------|--------|----------|---------|--------------------------------|
| `symbol`  | string | No       | ZEC     | 币种符号                       |
| `top_k`   | int    | No       | 50      | 返回相似案例的数量             |

**Response:**

```json
[
  {
    "date": "2023-05-15T00:00:00",
    "similarity": 0.95,
    "price": 140.0,
    "features": { ... }
  },
  ...
]
```

#### `GET /api/state/scenarios`

基于当前市场状态（价格趋势、波动率、注意力特征）寻找历史相似时刻，并统计后续走势分布。

**Query Parameters:**

| Parameter | Type   | Required | Default | Description                    |
|-----------|--------|----------|---------|--------------------------------|
| `symbol`  | string | No       | ZEC     | 币种符号                       |
| `top_k`   | int    | No       | 50      | 选取最相似的历史状态数量       |
| `lookahead`| int   | No       | 5       | 统计未来 N 天的收益表现        |

**Example Request:**

```bash
curl "http://localhost:8000/api/state/scenarios?symbol=ZEC&top_k=50&lookahead=5"
```

**Response:**

```json
{
  "current_state": {
    "date": "2024-03-20T00:00:00",
    "price": 150.5,
    "features": {
      "trend_7d": 0.05,
      "volatility_30d": 0.02,
      "attention_score": 75.0
    }
  },
  "scenarios": [
    {
      "label": "trend_up",
      "probability": 0.45,
      "avg_return": 0.08,
      "count": 22
    },
    {
      "label": "sideways",
      "probability": 0.35,
      "avg_return": 0.01,
      "count": 18
    },
    {
      "label": "trend_down",
      "probability": 0.20,
      "avg_return": -0.05,
      "count": 10
    }
  ],
  "similar_dates": [
    {
      "date": "2023-05-15T00:00:00",
      "similarity": 0.95,
      "return_lookahead": 0.07
    },
    {
      "date": "2022-11-08T00:00:00",
      "similarity": 0.92,
      "return_lookahead": -0.02
    }
  ]
}
```

---

## 🔧 Error Handling

所有端点在出错时返回标准的 HTTP 错误响应:

**400 Bad Request:**
```json
{
  "detail": "Invalid timeframe: 99h. Must be one of: 15m, 1h, 4h, 1d"
}
```

**404 Not Found:**
```json
{
  "detail": "Data not found for symbol: INVALID"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal server error: <error message>"
}
```

---

## 📅 Date/Time Format

所有日期时间参数和响应字段使用 **ISO 8601** 格式:

- **格式:** `YYYY-MM-DDTHH:MM:SSZ`
- **时区:** UTC
- **示例:** `2024-01-01T00:00:00Z`

JavaScript 示例:
```javascript
const start = new Date('2024-01-01').toISOString()  // "2024-01-01T00:00:00.000Z"
const end = new Date().toISOString()                 // Current time
```

Python 示例:
```python
from datetime import datetime, timezone

start = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()  # "2024-01-01T00:00:00+00:00"
end = datetime.now(timezone.utc).isoformat()                    # Current time
```

---

## 🚀 Usage Examples

### JavaScript/TypeScript (Frontend)

```typescript
// 获取最近 30 天的价格数据
const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()
const now = new Date().toISOString()

const response = await fetch(
  `http://localhost:8000/api/price?symbol=ZECUSDT&timeframe=1d&start=${thirtyDaysAgo}&end=${now}`
)
const priceData = await response.json()

// 获取注意力数据
const attentionResponse = await fetch(
  `http://localhost:8000/api/attention?symbol=ZEC&start=${thirtyDaysAgo}`
)
const attentionData = await attentionResponse.json()
```

### Python (Backend Integration)

```python
import requests
from datetime import datetime, timedelta, timezone

# 获取最近 7 天的数据
end = datetime.now(timezone.utc)
start = end - timedelta(days=7)

# 价格数据
price_response = requests.get(
    'http://localhost:8000/api/price',
    params={
        'symbol': 'ZECUSDT',
        'timeframe': '1d',
        'start': start.isoformat(),
        'end': end.isoformat()
    }
)
price_data = price_response.json()

# 注意力数据
attention_response = requests.get(
    'http://localhost:8000/api/attention',
    params={
        'symbol': 'ZEC',
        'start': start.isoformat()
    }
)
attention_data = attention_response.json()
```

### cURL (Testing)

```bash
# Health check
curl http://localhost:8000/health

# Get price data
curl "http://localhost:8000/api/price?symbol=ZECUSDT&timeframe=1d"

# Get attention data with time range
curl "http://localhost:8000/api/attention?symbol=ZEC&start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z"

# Get recent news
curl "http://localhost:8000/api/news?symbol=ZEC"
```

---

## 🔐 CORS Configuration

The API is configured to allow cross-origin requests from any origin (`allow_origins=["*"]`).

**Allowed Methods:** GET, POST, PUT, DELETE, OPTIONS  
**Allowed Headers:** All  
**Credentials:** Not supported

For production deployment, update CORS settings in `src/api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Restrict to specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## 📈 Data Flow

```
┌─────────────────┐
│  Next.js        │
│  Frontend       │
│  (Port 3000)    │
└────────┬────────┘
         │ HTTP Request
         │ GET /api/price
         ▼
┌─────────────────┐
│  FastAPI        │
│  Backend        │
│  (Port 8000)    │
└────────┬────────┘
         │
         ├──► src/data/storage.py (DB Access)
         │
         ├──► src/data/price_fetcher.py (Fetch if missing)
         │
         ├──► src/features/attention_fetcher.py
         │
         └──► src/features/attention_features.py
              │
              ▼
         ┌──────────────┐
         │  PostgreSQL  │
         │  Database    │
         └──────────────┘
```

---

## 🛠️ Development Tips

### 1. 自动重载

使用 `--reload` 标志启动服务器可在代码更改时自动重启:

```bash
uvicorn src.api.main:app --reload --port 8000
```

### 2. 查看日志

FastAPI 会在控制台输出详细的请求日志:

```
INFO:     127.0.0.1:52345 - "GET /api/price?symbol=ZECUSDT HTTP/1.1" 200 OK
```

### 3. 交互式 API 文档

访问 `http://localhost:8000/docs` 可以:
- 查看所有端点
- 测试 API 调用
- 查看请求/响应模型
- 下载 OpenAPI schema

### 4. 数据缓存

API 会自动检查数据是否存在:
- 如果数据库中数据不存在,会调用 `fetch_and_save_price()` 自动获取
- 如果注意力数据不存在,会调用 `fetch_zec_news()` + `process_attention_features()`

---

## 📝 Notes

1. **时区:** 所有时间戳都是 UTC 时区
2. **数据来源:** 价格数据来自 Binance,新闻数据来自 CryptoPanic/NewsAPI
3. **限流:** 当前无限流,生产环境建议添加速率限制
4. **认证:** 当前无认证,生产环境建议添加 API Key 或 OAuth2
5. **缓存:** 可考虑添加 Redis 缓存提升性能

---

## 🔗 Related Documentation

- [FastAPI Official Docs](https://fastapi.tiangolo.com/)
- [Uvicorn Deployment](https://www.uvicorn.org/deployment/)
- [OpenAPI Specification](https://swagger.io/specification/)
- [ISO 8601 Date Format](https://en.wikipedia.org/wiki/ISO_8601)

---

## 🧪 Research: Attention Regimes

`POST /api/research/attention-regimes`

对多个 symbol 的注意力分位数分层，统计未来对数收益的分布特征，可在前端研究页或 Notebook 中复用。

**Request Body 字段**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `symbols` | string[] | ✅ | - | 币种列表（自动转成大写、去空值）。|
| `lookahead_days` | int[] &#124; string | ❌ | `[7,30]` | 未来收益窗口，支持列表或逗号分隔字符串，仅保留正整数。|
| `attention_source` | string | ❌ | `composite` | 选择注意力通道，`composite` 、`news_channel`、`google_channel` 等。|
| `split_method` | string | ❌ | `tercile` | `tercile` / `quartile` / `custom`。custom 时需提供 `split_quantiles`。|
| `split_quantiles` | float[] | ❌ | - | 自定义分位点（0-1），例如 `[0,0.2,0.5,0.8,1]`。自动补齐缺失的 0/1。|
| `start` / `end` | string | ❌ | - | ISO8601 时间范围，缺省则使用全量。|

**Example Request**

```json
{
  "symbols": ["ZEC", "BTC", "ETH"],
  "lookahead_days": [7, 30],
  "attention_source": "composite",
  "split_method": "custom",
  "split_quantiles": [0.0, 0.2, 0.5, 0.8, 1.0],
  "start": "2023-01-01T00:00:00Z",
  "end": "2024-12-31T23:59:59Z"
}
```

**Response**

```json
{
  "meta": {
    "symbols": ["ZEC", "BTC", "ETH"],
    "lookahead_days": [7, 30],
    "attention_source": "composite",
    "split_method": "custom",
    "start": "2023-01-01T00:00:00+00:00",
    "end": "2024-12-31T23:59:59+00:00"
  },
  "results": {
    "ZEC": {
      "meta": {
        "attention_source": "composite",
        "split_method": "custom",
        "lookahead_days": [7, 30],
        "data_points": 480
      },
      "regimes": [
        {
          "name": "q1",
          "quantile_range": [0.12, 0.35],
          "stats": {
            "7": {"avg_return": 0.0081, "std_return": 0.045, "pos_ratio": 0.56, "sample_count": 120},
            "30": {"avg_return": 0.041, "std_return": 0.11, "pos_ratio": 0.61, "sample_count": 112}
          }
        },
        {
          "name": "q2",
          "quantile_range": [0.35, 0.51],
          "stats": {"7": {"avg_return": 0.004, "std_return": 0.034, "pos_ratio": 0.52, "sample_count": 118}}
        }
      ]
    },
    "BTC": {
      "meta": {"error": "missing data"},
      "regimes": []
    }
  }
}
```

**说明**
- `results.<symbol>.meta.error` 在缺失数据或分位计算失败时返回原因，便于前端提示。
- `quantile_range` 为数值区间（注意力原始值），`stats` key 为字符串化的 `lookahead_days`。
- 每个 `stats` 节点包含 `avg_return`（对数收益均值）、`std_return`（样本标准差）、`pos_ratio`（正收益占比）与 `sample_count`。
- 输入无效时（如空 symbol、非法分位）API 返回 `400`，其它异常返回 `500`。
