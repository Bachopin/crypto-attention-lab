# Crypto Attention Lab - Web Frontend

## 📁 Project Overview

This is a professional, production-ready Next.js dashboard for cryptocurrency attention analysis. The frontend is completely independent from the Python backend and communicates via REST APIs.

```
crypto-attention-lab/
├── src/                    # Python backend
│   ├── dashboard/         # Streamlit app (existing)
│   ├── data/              # Data fetchers
│   └── features/          # Feature engineering
├── data/                  # Data storage
└── web/                   # 🆕 Next.js frontend (THIS PROJECT)
    ├── app/              
    │   ├── layout.tsx     # Root layout
    │   ├── page.tsx       # Main dashboard
    │   └── globals.css    # Tailwind styles
    ├── components/
    │   ├── ui/           # Base UI components
    │   ├── PriceChart.tsx # TradingView chart
    │   ├── StatCards.tsx  # Metrics cards
    │   ├── BacktestPanel.tsx # Basic attention backtest with risk controls
    │   └── NewsList.tsx   # News feed
    ├── lib/
    │   ├── api.ts        # API layer (mock + real)
    │   └── utils.ts      # Utilities
    └── README.md         # Full documentation
```

## 🎯 Key Features

### 1. **Professional Trading UI**
- Dark theme optimized for trading terminals
- TradingView-style candlestick charts with volume
- Attention score overlay on price charts
- Responsive grid layout

### 2. **Three-Layer Dashboard Structure**

**Layer 1 - Top Summary**
- Main asset card (ZEC/USDT) with current price & 24h change
- 4 metric cards: News Count, Avg Attention, Volatility, Price Change

**Layer 2 - Middle Panels**
- Price overview (90-day trend)
- Recent news feed (5 latest items)

**Layer 3 - Bottom Charts**
- Full TradingView chart with timeframe selector (1D/4H/1H/15M)
- Combined candlestick + volume + attention line
- Full news list

### 3. **Technology Stack**
- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript (full type safety)
- **Styling**: Tailwind CSS + CSS Variables
- **Components**: Shadcn UI (Radix primitives)
- **Charts**: lightweight-charts (TradingView)
- **Icons**: Lucide React

### 4. **API Integration Ready**
- Mock data generators for development
- Clean API abstraction layer
- Type-safe interfaces matching Python backend
- Easy switch from mock to production

## 🚀 Quick Start

### Prerequisites
```bash
node --version  # >= 18.0.0
npm --version   # >= 9.0.0
```

### Installation
```bash
cd web
npm install
npm run dev
```

Visit: **http://localhost:3000**

## 🔌 Backend Integration Guide

### Step 1: Create Python FastAPI Endpoints

The frontend expects these endpoints (currently using mock data):

```python
# Example FastAPI implementation (create in Python project)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/price")
def get_price(symbol: str, timeframe: str):
    # Load from your existing price_fetcher.py
    return [
        {
            "timestamp": 1234567890000,
            "open": 45.23,
            "high": 46.50,
            "low": 44.80,
            "close": 45.90,
            "volume": 123456
        }
    ]

@app.get("/api/attention")
def get_attention(symbol: str, granularity: str):
    # Load from attention_features.py
    return [...]

@app.get("/api/news")
def get_news(symbol: str):
    # Load from attention_fetcher.py
    return [...]
```

### Step 2: Update Frontend API Calls

In `web/lib/api.ts`, uncomment real API calls:

```typescript
export async function fetchPrice(params: FetchPriceParams): Promise<PriceCandle[]> {
  const response = await fetch(
    `${API_BASE_URL}/price?symbol=${params.symbol}&timeframe=${params.timeframe}`
  );
  return await response.json();
}
```

### Step 3: Configure API URL

Create `web/.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

## 📊 Component Architecture

### PriceChart Component
- Uses `lightweight-charts` library
- Displays candlestick data
- Supports event markers overlay
- Synchronized with Volume and Attention charts via crosshair

### AttentionRegimePanel Component (New)
- Multi-symbol attention regime analysis interface
- Displays regime statistics (avg return, win rate) across different lookahead periods
- Supports custom parameters (lookahead days, split method)
- **Smart Analysis Report**: Automatically generates text-based insights (Momentum/Reversal/Diminishing Returns) based on regime performance differences

### StatCards Components
- **SummaryCard**: Main asset display with gradient background
- **StatCard**: Reusable metric card with optional change indicator
- Color-coded positive/negative changes

### NewsList Component
- Scrollable news feed
- Timestamp formatting with date-fns
- External link indicators
- Source badges

### BacktestPanel Component
- Basic attention factor backtest UI
- Exposes risk parameters: `stop_loss_pct`, `take_profit_pct`, `max_holding_days`, `position_size`
- Supports single-asset and multi-asset backtests via `/api/backtest/basic-attention` 与 `/api/backtest/basic-attention/multi`
- Visualizes backtest `equity_curve` as a lightweight inline SVG line chart (single-asset, per-symbol multi-asset, and multi-strategy comparison)
- Supports multiple named strategy presets stored in `localStorage` with prefix `basic-attention-preset-<name>`, including all key parameters
- Maintains per-preset last backtest summary and equity curve in `localStorage` (`basic-attention-summary-<name>`, `basic-attention-equity-<name>`) and exposes a "策略概览" table (sortable by cumulative return)
- Allows selecting up to 3 presets for multi-strategy equity curve comparison in a shared SVG chart

#### Attention Condition (策略 Preset 扩展)
- **New Feature**: 支持 `AttentionCondition` 配置，使用 Regime 驱动的入场信号
- 用户可选择注意力来源 (`composite` / `news_channel`) 和 Regime 档位 (`low` / `mid` / `high` / `custom`)
- `custom` 模式支持自定义分位区间 (lower/upper quantile)
- Preset 管理：保存、加载、删除策略配置到 `localStorage`
- 回测结果显示 Condition Summary（如 "Composite, high, 30d"）
- 多策略对比表格中包含 Condition 摘要列

**相关文件**:
- `web/lib/presets.ts`: `useStrategyPresets()` hook 和 `formatConditionSummary()` 工具函数
- `web/lib/api.ts`: `AttentionCondition` 和 `StrategyPreset` 类型定义
- `web/components/BacktestPanel.tsx`: UI 实现

## 🎨 Theming

The project uses CSS variables for theming (see `app/globals.css`):

```css
:root {
  --background: 222.2 84% 4.9%;  /* Dark background */
  --foreground: 210 40% 98%;      /* Light text */
  --primary: 217.2 91.2% 59.8%;   /* Blue accent */
  --chart-green: #26a69a;         /* Bullish */
  --chart-red: #ef5350;           /* Bearish */
}
```

Customize in `tailwind.config.ts`.

## 🔧 Development Tips

### Hot Reload
Next.js automatically reloads on file changes. No need to restart the server.

### Type Safety
All API responses are typed. TypeScript will catch mismatches:

```typescript
const data: PriceCandle[] = await fetchPrice(...)
// data[0].close ✅
// data[0].closing ❌ Type error
```

### Mock vs Production
Toggle between mock and real data by commenting/uncommenting in `lib/api.ts`.

## 📦 Build for Production

```bash
npm run build
npm run start
```

Output is optimized and minified in `.next/` directory.

## 🐛 Common Issues

### "Module not found: react"
```bash
rm -rf node_modules package-lock.json
npm install
```

### Port 3000 already in use
```bash
npm run dev -- -p 3001
```

### Chart not rendering
Check browser console. Ensure `priceData` and `attentionData` have correct timestamp formats (Unix ms).

## 🗺️ Roadmap

- [ ] Add WebSocket support for real-time updates
- [ ] Implement user authentication
- [ ] Add more technical indicators to charts
- [ ] Create admin panel for data management
- [ ] Mobile-optimized responsive design
- [ ] Export功能 (CSV, PDF reports)
- [ ] Multi-symbol support (not just ZEC)
- [ ] Historical data comparison tool

## 📞 Support

For questions about:
- **Frontend**: Check `web/README.md`
- **Backend Integration**: See Python project docs
- **API Schema**: Review type definitions in `lib/api.ts`

---

**Built with ❤️ for professional crypto traders and researchers**
