# Crypto Attention Lab

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Next.js](https://img.shields.io/badge/Next.js-15.0+-black.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

**Crypto Attention Lab** 是一个全栈量化研究平台，专注于探索**市场注意力（Attention）**与**加密货币价格**之间的关系。通过聚合新闻、社交媒体和搜索趋势数据，构建多维注意力因子，并提供可视化的回测与情景分析工具。

---

## 🚀 快速开始

### 1. 启动全栈环境 (推荐)
一键启动 FastAPI 后端 (8000) 和 Next.js 前端 (3000)：
```bash
./scripts/dev.sh
```

### 2. 访问应用
- **Web 看板**: [http://localhost:3000](http://localhost:3000)
- **API 文档**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. 获取真实数据
首次使用请参考 [数据获取指南](docs/backend/DATA_PIPELINE.md) 配置 API Key。

---

## ✨ 核心功能

- **📈 多维注意力因子**: 融合 News, Google Trends, Twitter 的复合注意力指标。
- **🧠 情景分析 (Scenario Analysis)**: 基于历史相似状态（价格/波动率/注意力）推演未来走势。
- **⚡ 实时数据流**: WebSocket 推送秒级价格与分钟级注意力更新。
- **🧪 交互式回测**: 在前端直接调整策略参数（阈值、止损止盈），实时查看权益曲线。
- **🔍 自动数据对齐**: 智能补齐多源异构数据的时间戳，确保分析准确性。

---

## 📚 文档索引

详细文档请查阅 `docs/` 目录：

### 🏁 入门指南 (Setup)
- [**快速开始 (Quickstart)**](docs/setup/QUICKSTART.md): 环境配置与详细启动步骤。
- [**系统运行 (System Running)**](docs/setup/SYSTEM_RUNNING.md): 常见运行模式与故障排除。
- [**权重更新指南**](docs/setup/WEIGHT_UPDATE_GUIDE.md): 新闻源权重更新后的数据重算流程。

### ⚙️ 后端与数据 (Backend)
- [**架构概览 (Architecture)**](docs/backend/ARCHITECTURE.md): 系统设计与数据流向。
- [**API 参考 (API Reference)**](docs/backend/API_REFERENCE.md): 核心 API 端点说明。
- [**数据管道 (Data Pipeline)**](docs/backend/DATA_PIPELINE.md): 真实数据获取与数据库迁移。
- [**自动更新机制**](docs/backend/AUTO_UPDATE_PIPELINE.md): 后台任务调度详解（价格/新闻/特征增量更新）。
- [**内存优化**](docs/backend/MEMORY_OPTIMIZATION.md): 内存泄露修复与监控工具。

### 🖥️ 前端开发 (Frontend)
- [**前端概览 (Overview)**](docs/frontend/OVERVIEW.md): Next.js 架构与组件集成。
- [**性能优化 (Optimization)**](docs/frontend/OPTIMIZATION.md): 渲染性能与状态管理最佳实践。

### 🔬 量化研究 (Research)
- [**注意力因子指南**](docs/research/ATTENTION_FACTORS.md): 因子定义、计算逻辑与 Regime 分析方法论。
- [**新闻数据源**](docs/research/NEWS_SOURCES.md): 支持的新闻源列表与权重配置。

---

## 🏗️ 项目结构

```
crypto-attention-lab/
├── docs/                  # 📚 项目文档 (New!)
├── src/                   # 🐍 Python 后端核心
│   ├── api/               # FastAPI 路由与入口
│   ├── data/              # 数据获取与存储
│   ├── features/          # 特征工程与因子计算
│   └── backtest/          # 回测引擎
├── web/                   # ⚛️ Next.js 前端应用
│   ├── app/               # 页面路由
│   ├── components/        # UI 组件
│   ├── lib/               # API 客户端 + WebSocket + Services
│   └── types/             # TypeScript 类型中心
├── scripts/               # 🛠️ 运维与数据脚本
└── data/                  # 💾 本地数据存储 (SQLite/CSV)
```

## 🗺️ 路线图

- [x] 基础数据管道 (Price + News)
- [x] 多维注意力特征工程
- [x] 交互式回测引擎
- [x] Scenario Analysis (相似状态分析)
- [x] WebSocket 实时推送
- [ ] 机器学习预测模型集成
- [ ] 实盘信号推送

## 📝 许可

本项目用于加密货币市场研究与教育目的。
