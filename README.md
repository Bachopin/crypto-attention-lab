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

### 首次使用：数据准备

如果是首次使用或想要使用数据库模式，请先运行数据迁移：

```bash
# 1. 迁移历史 CSV 数据到 SQLite 数据库
python scripts/migrate_to_database.py

# 2. 如需更新数据，运行以下脚本
python scripts/fetch_news_data.py        # 获取最新新闻
python scripts/fetch_price_data.py       # 获取价格数据
python scripts/generate_attention_data.py # 生成注意力特征
```

### 选项 1: 运行完整的全栈应用 (推荐) 🌟

```bash
# 使用一键启动脚本启动 FastAPI 后端 + Next.js 前端
./scripts/start_dev.sh

# 访问:
# - Next.js 前端: http://localhost:3000
# - FastAPI 后端: http://localhost:8000
# - API 文档: http://localhost:8000/docs
```

> 💡 `./scripts/start_services.sh` 也可以用来启动后端 + 前端，脚本在健康检查失败时会重试最多 10 次（默认每次间隔 3 秒），并把日志写入 `logs/api.log` 与 `logs/frontend.log`，方便调试启动顺序较慢的任务。

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
  - 参数: `symbol`, `start`, `end`, `limit`, `before`, `source`
  - 返回: 结构化新闻数据 (datetime, source, title, url, relevance, source_weight, sentiment_score, tags)
- ✅ **GET /api/news/count** - 获取新闻总数
  - 参数: `symbol`, `start`, `end`, `source`
  - 返回: `{ total: number }`
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
- ✅ 集成 CryptoPanic/NewsAPI/CryptoCompare/RSS 获取真实新闻
- ✅ 新闻特征工程（来源权重/相关性/情绪/标签）
- ✅ 多维注意力特征（weighted/bullish/bearish/event_intensity）
- ✅ 注意力事件检测（基于分位数阈值）
- ✅ 基础注意力策略回测框架
- ✅ 数据库存储（SQLite + SQLAlchemy，支持多币种扩展）
- ✅ CSV 向后兼容（数据迁移脚本）
- ✅ 支持多时间周期 (1D/4H/1H/15M)
- ✅ 代理支持 (HTTP/SOCKS5)

### Next.js 前端功能
- ✅ 专业交易终端 UI (暗色主题)
- ✅ TradingView 风格的 K 线图 + 成交量
- ✅ 注意力分数曲线叠加
- ✅ 注意力事件标注（可开关）
- ✅ 事件时间轴列表
- ✅ 交互式回测面板（参数调节 + 结果展示）
  - 支持单币种与多币种基础注意力回测
  - 暴露风控参数：止损/止盈/最长持仓天数/仓位大小
  - 内联 SVG 权益曲线展示（单标的 + 多标的单独切换）
  - 多命名策略 preset，本地 `localStorage` 存储与切换
  - 策略概览视图：按累计收益排序展示各策略最近一次回测 summary（交易数/胜率/累计收益/最大回撤）
  - 多策略权益曲线对比：可勾选最多 3 个策略在同一图上对比 equity curve
- ✅ **Attention Regime 分析面板** (新增)
  - 多币种注意力体制分析
  - 自定义前瞻天数与分位点方法
  - 可视化展示不同体制下的平均收益与胜率
- ✅ **图表体验优化**
  - 独立的成交量图表 (Volume Chart)
  - 价格概览 (Price Overview) 固定为日线趋势
  - 丝滑的时间周期切换 (无 Loading 闪烁)
- ✅ 时间周期切换控件
- ✅ 实时新闻流（支持分页、筛选、无限滚动）
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
GET /api/news?symbol=ZEC&start=2024-01-01T00:00:00Z&end=2024-12-31T23:59:59Z&limit=50&source=CoinDesk
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

### 多维注意力特征工程
系统现已实现基于新闻的多维注意力特征，包括：

- **来源权重（source_weight）**：对不同新闻来源赋予不同权重（CoinDesk=1.0, CryptoPanic=0.8, RSS=0.5 等）
- **情绪分数（sentiment_score）**：基于标题关键词的简单情绪打分（-1~1）
- **相关性标签（relevance）**：direct（直接提及币种）/ related（相关主题）
- **主题标签（tags）**：自动提取 listing/hack/upgrade/partnership/regulation 等关键事件标签
- **加权注意力（weighted_attention）**：综合来源权重和相关性的复合指标
- **看涨/看跌注意力（bullish/bearish_attention）**：根据情绪分解的正负注意力强度
- **事件强度（event_intensity）**：当日是否出现高权重来源 + 强情绪 + 明确主题的复合事件标记（0/1）

### 注意力事件检测
基于分位数阈值的事件检测模块，可识别以下类型的显著事件：

- **attention_spike**：注意力分数突增（相对过去 N 天）
- **high_weighted_event**：加权注意力显著上升
- **high_bullish**：看涨注意力大幅上升
- **high_bearish**：看跌注意力大幅上升
- **event_intensity**：出现高质量复合事件（高权重来源 + 强情绪 + 明确标签）

### 基础注意力策略与回测
实现了第一版基于注意力因子的交易策略（**实验性质，不构成投资建议**）：

**策略逻辑**（可通过前端参数调整）：
1. 当某日的加权注意力（weighted_attention）超过过去 N 天的分位数阈值（默认 0.8）
2. 且当日涨幅未超过设定上限（默认 5%，避免追高）
3. 且看涨注意力 > 看跌注意力
4. 则在该日收盘买入，持有 H 天（默认 3 天）后卖出

**回测输出**：
- 总交易次数、胜率、平均收益、累计收益、最大回撤
- 详细交易列表（入场/出场日期、价格、收益率）
- 简易 equity curve（初始资金 1.0，全仓进出）

### 前端可视化
- **价格图表事件标注**：在 K 线图上自动标记检测到的注意力事件：
  - high_bullish: 绿色向上箭头 ↑
  - high_bearish: 红色向下箭头 ↓
  - high_weighted_event/attention_spike/event_intensity: 黄色/蓝色圆点
  - 支持开关控制显示/隐藏事件标注
- **事件时间轴面板**：列表展示所有检测到的事件，含日期、类型、强度、新闻摘要
- **回测控制面板**：
  - 参数调节器（lookback_days、attention_quantile、max_daily_return、holding_days）
  - Summary 指标卡片（交易次数、胜率、平均收益、累计收益、最大回撤）
  - 详细交易表格
  - 一键运行回测按钮

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

### 数据管理

```bash
# 迁移 CSV 数据到数据库
python scripts/migrate_to_database.py

# 更新新闻数据
python scripts/fetch_news_data.py

# 更新价格数据
python scripts/fetch_price_data.py

# 生成注意力特征
python scripts/generate_attention_data.py
```

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

### 数据维护与清洗
```bash
# 清理异常价格数据 (如 timestamp=0)
python scripts/clean_bad_price_data.py

# 同步代币状态 (Active/Auto-update)
python scripts/sync_symbol_status.py
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
- [x] FastAPI 后端实现
- [x] 前后端完整集成
- [x] 多维注意力特征工程 🆕
- [x] 注意力事件检测 🆕
- [x] 基础注意力策略回测 🆕
- [x] 数据库存储（SQLite + 多币种支持）🆕
- [x] 前端事件可视化与交互式回测 🆕
- [x] 高级回测框架（止损/止盈/仓位管理）🆕
- [x] 多币种对比分析（基础版，多币种回测对比表）🆕
- [ ] WebSocket 实时数据流
- [ ] 机器学习预测模型集成
- [ ] 用户认证与个人策略保存
- [ ] 实盘信号推送

## 📝 许可

本项目用于加密货币市场研究与教育目的。

## 🙏 致谢

- [Binance API](https://binance-docs.github.io/apidocs/)
- [CryptoPanic](https://cryptopanic.com/)
- [Next.js](https://nextjs.org/)
- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/)
- [Streamlit](https://streamlit.io/)
