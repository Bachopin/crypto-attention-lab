# Crypto Attention Lab - Architecture Diagram

This diagram represents the current architecture of the backend system after the recent refactoring.

```mermaid
graph TD
    subgraph "API Layer (FastAPI)"
        API[src/api/main.py]
        Websocket[src/api/websocket_routes.py]
    end

    subgraph "Service Layer"
        MDS[src/services/market_data_service.py]
        AS[src/services/attention_service.py]
    end

    subgraph "Domain & Feature Logic"
        Calc[src/features/calculators.py]
        EventDet[src/features/event_detectors.py]
        NodeInf[src/features/node_influence.py]
        MathUtils[src/utils/math_utils.py]
    end

    subgraph "Data Access Layer"
        PriceFetcher[src/data/price_fetcher_binance.py]
        AttnFetcher[src/data/attention_fetcher.py]
        DB[src/data/db_storage.py]
        Storage[src/data/storage.py]
    end

    subgraph "Research & Backtest"
        Backtest[src/backtest/]
        Research[src/research/]
    end

    %% Relationships
    API --> MDS
    API --> AS
    
    MDS --> PriceFetcher
    MDS --> Storage
    
    AS --> AttnFetcher
    AS --> Calc
    AS --> EventDet
    AS --> NodeInf
    
    Calc --> MathUtils
    EventDet --> MathUtils
    NodeInf --> MathUtils
    
    Backtest --> MDS
    Backtest --> AS
    
    Research --> MDS
    Research --> AS
    Research --> MathUtils
```

## Key Components

### 1. API Layer
- **Entry Point**: `src/api/main.py`
- **Responsibilities**: Routing, Request Validation, Response Formatting.
- **Dependencies**: Calls into Service Layer.

### 2. Service Layer
- **MarketDataService**: Central hub for price data (OHLCV). Handles alignment and caching.
- **AttentionService**: Central hub for attention metrics and events. Orchestrates fetching, feature calculation, and event detection.

### 3. Domain & Feature Logic
- **Calculators (`src/features/calculators.py`)**: Pure functions for calculating attention metrics (z-scores, moving averages).
- **Event Detectors (`src/features/event_detectors.py`)**: Pure logic for detecting attention spikes and other events.
- **Math Utils (`src/utils/math_utils.py`)**: Shared mathematical primitives (rolling z-score, rolling quantile, safe percentage change) used across Features and Research.

### 4. Data Access Layer
- **Fetchers**: Interact with external APIs (Binance, Twitter, Google Trends).
- **Storage**: Manages local CSV/Parquet files and SQLite database.

### 5. Research & Backtest
- Consumers of the Service and Feature layers for analysis and strategy simulation.
