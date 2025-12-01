# System Architecture

This document describes the high-level architecture of the Crypto Attention Lab backend, following the refactoring to a modular Router-Service pattern.

## 🏗️ High-Level Architecture

The system is designed with a layered architecture to ensure separation of concerns, maintainability, and scalability.

```mermaid
graph TD
    Client[Web Frontend / External Clients] --> API_Gateway[FastAPI Entry Point (main.py)]
    Client <-->|WebSocket| WS_Price[/ws/price/]
    Client <-->|WebSocket| WS_Attn[/ws/attention/]

    subgraph "API Layer (Routers)"
        API_Gateway --> R_Market[Market Data Router]
        API_Gateway --> R_Attn[Attention Router]
        API_Gateway --> R_Backtest[Backtest Router]
        API_Gateway --> R_Research[Research Router]
        API_Gateway --> R_System[System Router]
    end

    subgraph "Service Layer"
        R_Market --> S_Market[MarketDataService]
        R_Attn --> S_Attn[AttentionService]
        R_Backtest --> S_Backtest[Backtest Engine]
        R_System --> S_Update[RealtimePriceUpdater]
        WS_Price --> S_BinanceWS[Binance WebSocket Manager]
    end

    subgraph "Domain Logic (Pure Python)"
        S_Attn --> L_Events[Event Detection Logic]
        S_Attn --> L_Features[Feature Engineering]
        S_Backtest --> L_Strategy[Strategy Templates]
        R_Research --> L_Scenarios[Scenario Engine]
    end

    subgraph "Data Layer"
        S_Market --> DB[(PostgreSQL / TimescaleDB)]
        S_Update --> Fetchers[Data Fetchers]
        Fetchers --> External[External APIs (Binance, News, etc.)]
    end
```

## 🧩 Module Descriptions

### 1. API Layer (`src/api/`)
The entry point for all external requests. It handles request validation, routing, and response formatting.

- **`main.py`**: The application entry point. It initializes the FastAPI app, configures middleware (CORS), manages the lifecycle of background tasks (Scheduler), and includes the routers.
- **`routers/`**: Contains domain-specific route definitions.
    - **`market_data.py`**: Endpoints for price history, news, symbols, and top coins.
    - **`attention.py`**: Endpoints for attention scores and attention events.
    - **`backtest.py`**: Endpoints for running strategy backtests.
    - **`research.py`**: Endpoints for advanced analysis (regimes, scenarios, state snapshots).
    - **`system.py`**: Endpoints for system health, auto-update management, and manual triggers.
    - **WebSocket Endpoints**: `/ws/price`, `/ws/attention` handled via `websocket_routes.py` with a global `ConnectionManager` for subscriptions and broadcasts.

### 2. Service Layer (`src/services/`)
Orchestrates business logic and data retrieval. It acts as a bridge between the API and the Data/Logic layers.

- **`MarketDataService`**: Centralized service for retrieving and aligning price and news data.
- **`AttentionService`**: Manages the calculation and retrieval of attention features (full & incremental modes).
- **`FeatureService`** (NEW): Provides cached loading of precomputed features with column whitelisting support, reducing API response latency.
- **`PrecomputationService`**: Manages state snapshots and event performance caching with configurable cooldowns.
- **`RealtimePriceUpdater`**: Handles the background synchronization of price data from external exchanges.
- **`Binance WebSocket Manager`** (`src/data/binance_websocket.py`): Manages realtime kline subscriptions and forwards 1m updates to WebSocket clients.

### 3. Domain Logic (`src/features/`, `src/events/`, `src/backtest/`)
Contains pure business logic, algorithms, and calculations. These modules are generally independent of the database and web framework.

- **`src/events/attention_events.py`**: Core logic for detecting attention anomalies and events.
- **`src/features/`**: Feature engineering logic (e.g., calculating moving averages, RSI, attention scores).
- **`src/backtest/`**: Strategy execution engines and performance calculation.

### 4. Data Layer (`src/data/`, `src/database/`)
Handles data persistence and external API interactions.

- **`src/database/models.py`**: SQLAlchemy ORM models.
- **`src/data/db_storage.py`**: Low-level database access functions.
- **`src/data/*_fetcher.py`**: Clients for external APIs (Binance, CryptoPanic, etc.).

## 🔄 Key Data Flows

### A. Request Processing
1.  **Client** sends a request (e.g., `GET /api/attention`).
2.  **`main.py`** routes it to **`routers/attention.py`**.
3.  **Router** calls **`AttentionService`**.
4.  **Service** queries the **Database** for raw data.
5.  **Service** may call **Domain Logic** to process raw data into features.
6.  **Service** returns structured data to the **Router**.
7.  **Router** returns JSON response to the **Client**.

### B. Background Updates
1.  **`main.py`** starts the `scheduled_price_update` task on startup.
2.  **Scheduler** triggers **`RealtimePriceUpdater`**.
3.  **Updater** fetches new data from **Binance**.
4.  **Updater** saves data to the **Database**.
5.  **Updater** triggers **`AttentionService`** to recalculate features for the new data points.

### C. Realtime Streaming
1. Client connects to `/ws/price` and subscribes to symbols.
2. `ConnectionManager` ensures Binance WS subscription and registers callbacks.
3. On each kline event, the manager normalizes data and broadcasts `{type: "price_update", symbol, data}` to subscribers.
4. Clients degrade gracefully: frontend hooks fallback to REST polling if WS is unavailable.
