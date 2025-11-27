# Crypto Attention Lab

## 🎯 项目目标
本项目旨在研究加密货币二级市场中「注意力（Attention）与价格」的关系。
长期目标是构建一个基于注意力机制的交易信号系统，通过识别关键影响力节点和事件来预测价格走势。

## 🏗️ 项目架构

本项目包含两个独立的应用:

### 1️⃣ Python 后端 + Streamlit Dashboard (现有)
- 数据获取与处理
- 特征工程
- 简单的 Streamlit 可视化界面

### 2️⃣ Next.js 专业前端 Dashboard (新增) 🆕
- 产品级交易终端界面
- TradingView 风格图表
- 响应式设计
- 完整的 TypeScript 类型安全

```
crypto-attention-lab/
├── src/                    # Python 后端
│   ├── data/              # 数据获取模块
│   ├── features/          # 特征工程
│   ├── dashboard/         # Streamlit 应用
│   └── config/            # 配置文件
├── data/                  # 数据存储
│   ├── raw/              # 原始数据
│   └── processed/        # 处理后数据
├── web/                   # 🆕 Next.js 前端
│   ├── app/              # Next.js 页面
│   ├── components/       # React 组件
│   ├── lib/              # API 与工具
│   └── README.md         # 前端详细文档
└── WEB_OVERVIEW.md       # 前端架构总览
```

## ⚠️ 重要提示: 获取真实新闻数据

**首次使用前必读!**

如果你看到新闻显示 "ZEC News Sample XXXX",说明系统正在使用 Mock 数据。

要获取真实新闻数据,需要配置 API 密钥:

```bash
# 1. 创建 .env 文件
cp .env.example .env

# 2. 编辑 .env 文件,添加你的 API key
# CRYPTOPANIC_API_KEY=your_key_here  # 推荐
# NEWS_API_KEY=your_key_here         # 可选

# 3. 删除旧的 mock 数据
rm data/raw/attention_zec_news.csv
rm data/processed/attention_features_zec.csv

# 4. 启动应用会自动获取真实数据
./scripts/start_dev.sh
```

**API 密钥获取方式:**
- **CryptoPanic:** https://cryptopanic.com/developers/api/ (免费版每天 1000 次)
- **NewsAPI:** https://newsapi.org/register (免费版每天 100 次)

📖 **详细说明:** [GET_REAL_DATA.md](./GET_REAL_DATA.md)

---

## 🚀 快速开始

### 选项 1: 运行完整的全栈应用 (推荐) 🌟

```bash
# 使用一键启动脚本启动 FastAPI 后端 + Next.js 前端
./scripts/start_dev.sh

# 访问:
# - Next.js 前端: http://localhost:3000
# - FastAPI 后端: http://localhost:8000
# - API 文档: http://localhost:8000/docs
```

### 选项 2: 分别启动后端和前端

#### 启动 FastAPI 后端

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 FastAPI
./scripts/start_api.sh

# 或手动启动
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 API 文档: **http://localhost:8000/docs**

#### 启动 Next.js 前端

```bash
cd web
npm install
npm run dev
```

访问前端: **http://localhost:3000**

### 选项 3: 运行 Streamlit Dashboard (旧版)

```bash
# 启动 Streamlit
streamlit run src/dashboard/app.py
```

访问: **http://localhost:8501**

## 📊 功能特性

### FastAPI 后端 API (新增) 🆕
- ✅ **GET /api/price** - 获取 OHLCV 价格数据
  - 参数: `symbol`, `timeframe`, `start`, `end`
  - 返回: 标准化的 K 线数据 (timestamp, open, high, low, close, volume)
- ✅ **GET /api/attention** - 获取注意力分数
  - 参数: `symbol`, `granularity`, `start`, `end`
  - 返回: 时间序列注意力分数 (0-100) + 新闻数量
- ✅ **GET /api/news** - 获取新闻列表
  - 参数: `symbol`, `start`, `end`
  - 返回: 结构化新闻数据 (datetime, source, title, url, relevance, source_weight, sentiment_score, tags)
- ✅ **GET /api/attention-events** - 获取注意力事件
  - 参数: `symbol`, `start`, `end`, `lookback_days`, `min_quantile`
  - 返回: `[{ datetime, event_type, intensity, summary }]`
- ✅ **POST /api/backtest/basic-attention** - 运行基础注意力策略回测
  - 入参: `symbol`, `lookback_days`, `attention_quantile`, `max_daily_return`, `holding_days`, `start`, `end`
  - 返回: `{ summary, trades, equity_curve }`
- ✅ 自动 CORS 配置 (支持跨域请求)
- ✅ 自动数据检查 (如果数据不存在自动获取)
- ✅ 完整的 API 文档 (FastAPI Swagger UI)

### Python 数据处理功能
- ✅ 从 Binance/CoinGecko 获取 ZEC 价格数据
- ✅ 集成 CryptoPanic/NewsAPI 获取真实新闻
- ✅ 新闻特征工程（来源权重/相关性/情绪/标签）
- ✅ 多维注意力特征（weighted/bullish/bearish/event_intensity）
- ✅ 支持多时间周期 (1D/4H/1H/15M)
- ✅ 代理支持 (HTTP/SOCKS5)

### Next.js 前端功能
- ✅ 专业交易终端 UI (暗色主题)
- ✅ TradingView 风格的 K 线图 + 成交量
- ✅ 注意力分数曲线叠加
- ✅ 时间周期切换控件
- ✅ 实时新闻流
- ✅ 关键指标卡片
- ✅ 响应式布局
- ✅ TypeScript 完整类型安全
- ✅ 错误处理和加载状态
- ✅ 连接到真实 FastAPI 后端

## 🔌 API 文档

### 后端 API 端点

FastAPI 后端提供以下 RESTful API 端点:

#### 1. 价格数据
```http
GET /api/price?symbol=ZECUSDT&timeframe=1d&start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z
```

**响应示例:**
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
  }
]
```

#### 2. 注意力分数
```http
GET /api/attention?symbol=ZEC&granularity=1d&start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z
```

**响应示例:**
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

#### 3. 新闻数据
```http
GET /api/news?symbol=ZEC&start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z
```

**响应示例:**
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

#### 4. 注意力事件 (新增)
```http
GET /api/attention-events?symbol=ZEC&lookback_days=30&min_quantile=0.8
```

事件类型枚举: `attention_spike | high_weighted_event | high_bullish | high_bearish | event_intensity`

**响应示例:**
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

#### 5. 基础注意力策略回测 (新增)
```http
POST /api/backtest/basic-attention
Content-Type: application/json

{
  "symbol": "ZECUSDT",
  "lookback_days": 30,
  "attention_quantile": 0.8,
  "max_daily_return": 0.05,
  "holding_days": 3
}
```

**响应示例:**
```json
{
  "summary": {
    "total_trades": 4,
    "win_rate": 50.0,
    "avg_return": 0.0021,
    "cumulative_return": 0.0086,
    "max_drawdown": 0.031
  },
  "trades": [
    {
      "entry_date": "2024-03-15",
      "exit_date": "2024-03-18",
      "entry_price": 28.34,
      "exit_price": 28.78,
      "return_pct": 0.0155
    }
  ],
  "equity_curve": [
    { "datetime": "2024-03-15", "equity": 1.0021 }
  ]
}
```

## 🧠 Attention 因子与事件 (前端可视化)

- 价格主图新增“事件标注”开关，基于 `attention-events` 在 K 线上方/下方打点：
  - high_bullish: 绿色向上箭头
  - high_bearish: 红色向下箭头
  - high_weighted_event/attention_spike/event_intensity: 黄色/蓝色圆点
- 事件列表与回测面板在首页中部区域可见，可交互运行回测并查看 Summary/Trades/EquityCurve。

#### 4. 健康检查
```http
GET /health
GET /ping
```

### 前端环境配置

在 `web/.env.local` 中配置后端地址:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### API 集成示例

前端通过统一的 API 客户端调用后端:

```typescript
import { fetchPrice, fetchAttention, fetchNews } from '@/lib/api'

// 获取价格数据
const priceData = await fetchPrice({
  symbol: 'ZECUSDT',
  timeframe: '1D',
  start: '2024-01-01T00:00:00Z',
  end: '2024-12-31T23:59:59Z'
})

// 获取注意力数据
const attentionData = await fetchAttention({
  symbol: 'ZEC',
  granularity: '1d'
})

// 获取新闻数据
const newsData = await fetchNews({
  symbol: 'ZEC'
})
```

详细集成指南见: **[WEB_OVERVIEW.md](./WEB_OVERVIEW.md)**

## 📦 依赖说明

### Python 后端
```bash
ccxt              # 交易所数据
pandas            # 数据处理
streamlit         # Web 界面 (旧版)
requests          # HTTP 请求
python-dotenv     # 环境变量
fastapi>=0.109.0  # REST API 框架
uvicorn[standard] # ASGI 服务器
```

### Next.js 前端
```bash
next              # React 框架
typescript        # 类型安全
tailwindcss       # 样式
lightweight-charts # TradingView 图表
shadcn/ui         # UI 组件
```

## 📖 文档导航

- **[web/README.md](./web/README.md)** - 前端详细使用文档
- **[WEB_OVERVIEW.md](./WEB_OVERVIEW.md)** - 前端架构与集成指南
- **[src/dashboard/app.py](./src/dashboard/app.py)** - Streamlit 应用源码

## 🛠️ 开发工具

### Python 开发
```bash
# 激活虚拟环境
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# 运行 Streamlit
streamlit run src/dashboard/app.py
```

### 前端开发
```bash
cd web
npm run dev      # 开发服务器
npm run build    # 生产构建
npm run lint     # 代码检查
```

### 后端测试

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest -q
```

## 🐛 故障排除

### Streamlit 端口冲突
```bash
streamlit run src/dashboard/app.py --server.port 8502
```

### Next.js 端口冲突
```bash
cd web
npm run dev -- -p 3001
```

### 代理配置 (Binance API)
```bash
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890
```

## 🗺️ 路线图

- [x] 基础数据获取 (价格 + 新闻)
- [x] Streamlit 简单可视化
- [x] 真实新闻 API 集成
- [x] 专业级 Next.js 前端
- [x] FastAPI 后端实现 🆕
- [x] 前后端完整集成 🆕
- [ ] WebSocket 实时数据
- [ ] 用户认证系统
- [ ] 多币种支持
- [ ] 高级技术指标
- [ ] 交易信号生成
- [ ] 回测系统
- [ ] 预测模型集成

## 📝 许可

本项目用于加密货币市场研究与教育目的。

## 🙏 致谢

- [Binance API](https://binance-docs.github.io/apidocs/)
- [CryptoPanic](https://cryptopanic.com/)
- [Next.js](https://nextjs.org/)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Streamlit](https://streamlit.io/)
