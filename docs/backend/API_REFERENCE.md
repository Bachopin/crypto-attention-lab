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
- `symbol` (string, required): The trading pair symbol (e.g., "BTC", "ETH").
- `timeframe` (string, optional): Time granularity. Default: `1d`.
- `limit` (integer, optional): Number of data points to return. Default: `100`.

#### Get Latest Price
`GET /api/price/latest`

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

## Error Handling

The API uses standard HTTP status codes:
- `200 OK`: Request succeeded.
- `400 Bad Request`: Invalid parameters or validation error.
- `404 Not Found`: Resource (symbol/data) not found.
- `500 Internal Server Error`: Server-side processing error.

All error responses include a JSON body with a `detail` field explaining the error.
