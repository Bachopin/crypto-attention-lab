# Crypto Attention Lab - Web Dashboard

Professional cryptocurrency attention analysis dashboard built with Next.js, TypeScript, and TradingView-style charts.

## 🚀 Features

- **Modern Tech Stack**: Next.js 15 (App Router) + TypeScript + Tailwind CSS
- **Turbopack**: Lightning-fast development builds (~1-2s startup)
- **Professional UI**: Trading terminal-style dashboard with dark theme
- **Advanced Charts**: TradingView lightweight-charts for price action analysis
- **Real-time Data**: WebSocket support with REST API fallback
- **API Debug Page**: Built-in `/debug/api-test` for troubleshooting
- **Responsive Design**: Works seamlessly on desktop and mobile

## 📋 Prerequisites

- **Node.js**: >= 18.0.0
- **npm**: >= 9.0.0

Check your versions:
```bash
node --version
npm --version
```

## 🛠️ Installation

1. Navigate to the web directory:
```bash
cd web
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server (with Turbopack):
```bash
npm run dev
```

4. Open your browser and visit:
```
http://localhost:3000
```

## 🔧 Debug Tools

Visit `/debug/api-test` to test all API endpoints. This page helps diagnose:
- Backend connectivity issues
- Proxy configuration problems
- API response verification

## 📦 Project Structure

```
web/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Root layout with dark theme
│   ├── page.tsx           # Main dashboard page
│   └── globals.css        # Global styles & Tailwind
├── components/            # React components
│   ├── ui/               # Shadcn UI base components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   └── separator.tsx
│   ├── PriceChart.tsx    # TradingView chart component
│   ├── AttentionRegimePanel.tsx # Regime analysis with smart reports
│   ├── StatCards.tsx     # Summary & metric cards
│   └── NewsList.tsx      # News feed component
├── lib/                   # Utilities & API
│   ├── api.ts            # API functions & request cache
│   ├── websocket.ts      # WebSocket managers & hooks
│   └── services/         # Feature-oriented data orchestration (NEW)
├── types/                # Centralized TypeScript models (NEW)
├── public/               # Static assets
├── package.json          # Dependencies
├── tsconfig.json         # TypeScript config
├── tailwind.config.ts    # Tailwind configuration
└── next.config.ts        # Next.js configuration
```

## 🏗️ Frontend Architecture

The project follows a lightweight layered architecture to ensure maintainability and separation of concerns.

### 1. API Layer (`web/lib/api.ts`)
- **Responsibility**: Handles raw HTTP requests to the backend.
- **Convention**: 
  - Functions should map 1:1 to backend endpoints.
  - Returns typed responses (defined in `web/types/models.ts`).
  - Handles basic HTTP errors (status codes) and lightweight request cache (30s TTL).

### 2. Service Layer (`web/lib/services/`)
- **Responsibility**: Orchestrates data fetching and transformation for specific views or features.
- **Convention**:
  - Encapsulates complex fetching logic (e.g., parallel requests, progressive loading).
  - Transforms raw API data into View Models if necessary.
  - Example: `dashboard-service.ts` handles the loading strategy for the main dashboard.

### 3. Type Layer (`web/types/`)
- **Responsibility**: Centralized TypeScript definitions.
- **Structure**:
  - `models.ts`: Core domain entities (Candle, NewsItem, etc.) shared across the app.
  - `dashboard.ts`: Types specific to the dashboard view.

### 4. View Layer (`web/app/` & `web/components/`)
- **Responsibility**: UI rendering and user interaction.
- **Convention**:
  - Components should be "dumb" regarding data fetching details.
  - Use Services to get data.
  - Handle UI states: Loading, Error, Empty, Success.
  - Heavy components (charts) must be dynamically imported.

### 5. Realtime Layer (`web/lib/websocket.ts`) (NEW)
- **Responsibility**: WebSocket clients for price/attention, auto-reconnect, REST fallback.
- **Hooks**:
  - `useRealtimePrice(symbol)`: single-symbol realtime price (fallback polling on disconnect).
  - `useRealtimePrices(symbols)`: multi-symbol realtime prices.
  - `useRealtimeAttention(symbol)`: realtime attention and events.
  - `useWebSocketStatus()`: connection status indicator.
- **Config**: override default `ws://localhost:8000` via `NEXT_PUBLIC_WS_URL`.

## 🔌 Backend Integration

The project is pre-configured to connect with a Python backend API (default: `http://localhost:8000`).

### Expected API Endpoints

1. **Price Data**
   ```
   GET /api/price?symbol=ZECUSDT&timeframe=1h&start=...&end=...
   ```
   Response:
   ```json
   [
     {
       "timestamp": 1234567890000,
       "open": 45.23,
       "high": 46.50,
       "low": 44.80,
       "close": 45.90,
       "volume": 123456
     }
   ]
   ```

2. **Attention Score**
   ```
   GET /api/attention?symbol=ZEC&granularity=1d&start=...&end=...
   ```
   Response:
   ```json
   [
     {
       "timestamp": 1234567890000,
       "attention_score": 67.5,
       "news_count": 12
     }
   ]
   ```

3. **News Feed**
   ```
   GET /api/news?symbol=ZEC&start=...&end=...
   ```
   Response:
   ```json
   [
     {
       "datetime": "2025-11-27T08:00:00Z",
       "source": "CryptoPanic",
       "title": "ZEC Price Surges...",
       "url": "https://..."
     }
   ]
   ```

### Switching from Mock to Real API

The project now uses real API calls by default with error handling and a small request cache:
- Configure `NEXT_PUBLIC_API_BASE_URL` to point to your backend (e.g., `http://localhost:8000`).
- Use functions in `web/lib/api.ts`; they will prepend `/api/...` automatically.

## 🎨 Customization

### Theme Colors

Edit `tailwind.config.ts` to customize colors:

```typescript
colors: {
  'chart-green': '#26a69a',  // Bullish candles
  'chart-red': '#ef5350',    // Bearish candles
  'chart-grid': '#1f2937',   // Chart grid lines
}
```

### API Base URL

Set environment variables in `.env.local` (consistent with code in `web/lib/api.ts`):

```bash
NEXT_PUBLIC_API_BASE_URL=http://your-backend-url:8000
NEXT_PUBLIC_WS_URL=ws://your-backend-url:8000
```

## 📜 Available Scripts

- `npm run dev` - Start development server with Turbopack (fast)
- `npm run dev:webpack` - Start with webpack (if Turbopack has issues)
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint

## 🔧 Troubleshooting

### Port Already in Use

If port 3000 is taken, Next.js will automatically try 3001. Or specify manually:

```bash
npm run dev -- -p 3001
```

### Module Not Found

Clear cache and reinstall:

```bash
rm -rf node_modules package-lock.json
npm install
```

### WebSocket Connection Issues

- Ensure backend exposes `/ws/price` and `/ws/attention`.
- On cloud/proxy environments, set `NEXT_PUBLIC_WS_URL`.
- Check browser console and backend `/api/ws/stats` for connection status.

## 🚧 Next Steps

1. **Implement Python Backend API** - Create FastAPI endpoints matching the expected schema
2. **Add Authentication** - Implement user login/session management
3. **Real-time Updates** - WebSocket integrated; extend attention events
4. **Additional Indicators** - Enhance charts with technical indicators
5. **Export功能** - Add data export capabilities (CSV, PDF reports)

## 📝 License

This project is part of the Crypto Attention Lab research tool.

## 🙏 Acknowledgments

- [Next.js](https://nextjs.org/)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Shadcn UI](https://ui.shadcn.com/)
- [Tailwind CSS](https://tailwindcss.com/)
