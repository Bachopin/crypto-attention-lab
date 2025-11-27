# Crypto Attention Lab - Web Dashboard

Professional cryptocurrency attention analysis dashboard built with Next.js, TypeScript, and TradingView-style charts.

## 🚀 Features

- **Modern Tech Stack**: Next.js 15 (App Router) + TypeScript + Tailwind CSS
- **Professional UI**: Trading terminal-style dashboard with dark theme
- **Advanced Charts**: TradingView lightweight-charts for price action analysis
- **Real-time Data**: Ready for backend API integration
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

3. Start the development server:
```bash
npm run dev
```

4. Open your browser and visit:
```
http://localhost:3000
```

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
│   ├── StatCards.tsx     # Summary & metric cards
│   └── NewsList.tsx      # News feed component
├── lib/                   # Utilities & API
│   ├── api.ts            # API functions & mock data
│   └── utils.ts          # Helper functions
├── public/               # Static assets
├── package.json          # Dependencies
├── tsconfig.json         # TypeScript config
├── tailwind.config.ts    # Tailwind configuration
└── next.config.ts        # Next.js configuration
```

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

In `lib/api.ts`, uncomment the actual fetch calls and remove mock data returns:

```typescript
export async function fetchPrice(params: FetchPriceParams): Promise<PriceCandle[]> {
  const response = await fetch(
    `${API_BASE_URL}/price?symbol=${params.symbol}&timeframe=${params.timeframe}`
  );
  const data = await response.json();
  return data;
}
```

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

Set environment variable in `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://your-backend-url:8000/api
```

## 📜 Available Scripts

- `npm run dev` - Start development server
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

## 🚧 Next Steps

1. **Implement Python Backend API** - Create FastAPI endpoints matching the expected schema
2. **Add Authentication** - Implement user login/session management
3. **Real-time Updates** - Add WebSocket support for live price updates
4. **Additional Indicators** - Enhance charts with technical indicators
5. **Export功能** - Add data export capabilities (CSV, PDF reports)

## 📝 License

This project is part of the Crypto Attention Lab research tool.

## 🙏 Acknowledgments

- [Next.js](https://nextjs.org/)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Shadcn UI](https://ui.shadcn.com/)
- [Tailwind CSS](https://tailwindcss.com/)
