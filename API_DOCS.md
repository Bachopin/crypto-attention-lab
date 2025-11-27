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

运行基础注意力策略回测。

**Request Body:**

```json
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

**Response:**
```json
{
  "summary": {
    "total_trades": 5,
    "win_rate": 60.0,
    "avg_return": 0.045,
    "cumulative_return": 0.24,
    "max_drawdown": 0.10
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
         ├──► src/data/storage.py (Load CSV)
         │
         ├──► src/data/price_fetcher.py (Fetch if missing)
         │
         ├──► src/features/attention_fetcher.py
         │
         └──► src/features/attention_features.py
              │
              ▼
         ┌──────────────┐
         │  CSV Files   │
         │  data/raw/   │
         │  data/proc/  │
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
- 如果 CSV 文件不存在,会调用 `fetch_and_save_price()` 自动获取
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
