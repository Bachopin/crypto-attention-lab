# Crypto Attention Lab API Documentation

This document outlines the REST API endpoints available in the Crypto Attention Lab backend. The API is built using FastAPI and provides access to market data, attention metrics, research tools, and backtesting capabilities.

## Base URL

`http://localhost:8000`

## Authentication

Currently, the API does not require authentication for local development.

## Common Types

### Timeframe
- `1d`: Daily
- `4h`: 4-Hour
- `1h`: 1-Hour (where supported)
- `15m`: 15-Minute (where supported)

### Attention Source
- `legacy`: Original attention metric
- `composite`: Enhanced composite attention metric (Twitter + News + Google Trends)

---

## Endpoints

### 1. Market Data

#### Get Price Data
`GET /api/price`

Retrieve historical price data for a specific symbol.

**Parameters:**
- `symbol` (string, required): The trading pair symbol (e.g., "ZECUSDT", "BTCUSDT").
- `timeframe` (string, optional): Time granularity (`1d`, `4h`, `1h`, `15m`). Default: `1d`.
- `start` (string, optional): Start time in ISO8601 format.
- `end` (string, optional): End time in ISO8601 format.
- `limit` (integer, optional): Return the most recent N candles. If not specified, returns all data in the time range.

#### Get Latest Price
`GET /api/price/latest`
#### Get Top Coins (by market cap)
`GET /api/top-coins`

Retrieve top coins metadata from CoinGecko proxy.

**Parameters:**
- `limit` (integer, optional): Default `100`.

---

Retrieve the latest price for a specific symbol.

**Parameters:**
- `symbol` (string, required): The trading pair symbol.

---

### 2. Attention Metrics

#### Get Attention Data
`GET /api/attention`

Retrieve historical attention metrics for a specific symbol.

**Parameters:**
- `symbol` (string, required): The trading pair symbol.
- `timeframe` (string, optional): Time granularity. Default: `1d`.
- `limit` (integer, optional): Number of data points to return. Default: `100`.

#### Get Global Attention
`GET /api/attention/global`
#### Get Attention Events
`GET /api/attention-events`

Retrieve detected attention events for a symbol and period.

**Parameters:**
- `symbol` (string, optional): Default `ZEC`.
- `start` (string, optional): ISO datetime.
- `end` (string, optional): ISO datetime.
- `lookback_days` (integer, optional): Default `30`.
- `min_quantile` (number, optional): Default `0.8`.

#### Get Attention Event Performance
`GET /api/attention-events/performance`

Aggregate performance stats around attention events.

**Parameters:**
- `symbol` (string, optional): Default `ZEC`.
- `lookahead_days` (string, optional): CSV, e.g. `"1,3,5,10"`.

---

Retrieve global market attention metrics.

**Parameters:**
- `limit` (integer, optional): Number of data points to return. Default: `100`.

---

### 3. Research Tools

#### Attention Regimes Analysis
`POST /api/research/attention-regimes`

Analyze how different attention regimes affect future price returns.

**Request Body:**
```json
{
  "symbols": ["BTC", "ETH", "SOL"],
  "lookahead_days": [7, 30],
  "attention_source": "composite",
  "split_method": "tercile",
  "split_quantiles": [0.33, 0.67],
  "start": "2023-01-01",
  "end": "2023-12-31"
}
```

#### Get State Snapshot
`GET /api/state/snapshot`

Get the current market state snapshot for a symbol, including price trends and attention factors.

**Parameters:**
- `symbol` (string, required): The trading pair symbol.
- `timeframe` (string, optional): Time granularity. Default: `1d`.
- `window_days` (integer, optional): Feature calculation window. Default: `30`.

#### Batch State Snapshots
`POST /api/state/snapshot/batch`

Get state snapshots for multiple symbols at once.

**Request Body:**
```json
{
  "symbols": ["BTC", "ETH"],
  "timeframe": "1d",
  "window_days": 30
}
```

#### Find Similar Historical States
`GET /api/state/similar-cases`

Find historical market states that are similar to the current state of a symbol.

**Parameters:**
- `symbol` (string, required): Target symbol.
- `timeframe` (string, optional): Default `1d`.
- `top_k` (integer, optional): Number of similar cases to find. Default `50`.

#### Scenario Analysis
`GET /api/state/scenarios`
#### Node Influence (Carry Factor)
`GET /api/node-influence`

List high-influence nodes around attention events.

**Parameters:**
- `symbol` (string, optional)
- `min_events` (integer, optional): Default `10`
- `sort_by` (string, optional): `ir` | `mean_excess_return` | `hit_rate` (Default `ir`)
- `limit` (integer, optional): Default `100`

---

Perform scenario analysis based on similar historical states to project potential future outcomes.

**Parameters:**
- `symbol` (string, required): Target symbol.
- `timeframe` (string, optional): Default `1d`.
- `top_k` (integer, optional): Number of samples for analysis. Default `100`.

---

### 4. Backtesting

#### Basic Attention Strategy
`POST /api/backtest/basic-attention`

Backtest a single-asset strategy based on attention thresholds.

**Request Body:**
```json
{
  "symbol": "BTC",
  "lookback_days": 30,
  "attention_quantile": 0.8,
  "holding_days": 3,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.1,
  "start": "2023-01-01",
  "end": "2023-12-31"
}
```

#### Multi-Asset Basic Strategy
`POST /api/backtest/basic-attention/multi`

Run the basic attention strategy across multiple assets.

**Request Body:**
```json
{
  "symbols": ["BTC", "ETH", "SOL"],
  "lookback_days": 30,
  "attention_quantile": 0.8,
  "holding_days": 3
}
```

#### Attention Rotation Strategy
`POST /api/backtest/attention-rotation`

Backtest a portfolio rotation strategy that selects assets based on attention metrics.

**Request Body:**
```json
{
  "symbols": ["BTC", "ETH", "SOL", "AVAX"],
  "top_k": 3,
  "rebalance_days": 7,
  "lookback_days": 30,
  "initial_capital": 10000
}
```

---

### 5. News & Trends

#### Get News
`GET /api/news`

**Parameters:**
- `symbol` (string, optional): `ALL` for global
- `start`, `end` (ISO datetime, optional)
- `limit` (integer, optional)
- `before` (ISO datetime, optional)
- `source` (string, optional)

#### Get News Count
`GET /api/news/count`

Return only the total count for the given filters.

#### Get News Trend
`GET /api/news/trend`

Aggregated trend series for news volume and attention scores.

**Parameters:**
- `symbol` (string, optional): Default `ALL`
- `start`, `end` (ISO datetime, optional)
- `interval` (string, optional): `1h` | `1d` (Default `1d`)

---

### 6. WebSocket Endpoints

Base WS URL: `ws://localhost:8000`

#### Realtime Price Stream
`/ws/price`

Client → Server:
```json
{ "action": "subscribe", "symbols": ["BTC", "ETH"] }
{ "action": "unsubscribe", "symbols": ["BTC"] }
{ "action": "ping" }
```

Server → Client:
```json
{ "type": "price_update", "symbol": "BTC", "data": { "timestamp": 0, "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0, "is_closed": false } }
{ "type": "subscribed", "symbols": ["BTC"] }
{ "type": "pong" }
{ "type": "error", "message": "..." }
```

#### Realtime Attention Stream
`/ws/attention`

Client → Server:
```json
{ "action": "subscribe", "symbols": ["BTC"] }
{ "action": "ping" }
```

Server → Client:
```json
{ "type": "attention_update", "symbol": "BTC", "data": {"timestamp": 0, "attention_score": 0, "news_count": 0} }
{ "type": "attention_event", "symbol": "BTC", "event": {"event_type": "attention_spike", "intensity": 2, "summary": "..."} }
```

#### WebSocket Stats (HTTP)
`GET /api/ws/stats`

Returns current client counts, Binance connection status and subscriptions.

---

### 7. System & Health

#### Health Check
`GET /health`, `GET /ping`

Return service status and WebSocket connectivity summary.

#### Root
`GET /`

Lists common endpoints and service metadata.

---

## Error Handling

The API uses standard HTTP status codes:
- `200 OK`: Request succeeded.
- `400 Bad Request`: Invalid parameters or validation error.
- `404 Not Found`: Resource (symbol/data) not found.
- `500 Internal Server Error`: Server-side processing error.

All error responses include a JSON body with a `detail` field explaining the error.
