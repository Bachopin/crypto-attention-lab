# Copilot Instructions for Crypto Attention Lab

## 项目架构与核心模块
- **后端（Python, FastAPI）**：位于 `src/`，核心 API 入口为 `src/api/main.py`，数据处理在 `src/data/`、特征工程在 `src/features/`，配置在 `src/config/settings.py`。
- **前端（Next.js, TypeScript）**：位于 `web/`，主入口 `web/app/`，API 客户端在 `web/lib/api.ts`，UI 组件在 `web/components/`。
- **数据目录**：原始数据在 `data/raw/`，处理后数据在 `data/processed/`。
- **脚本**：自动化与开发脚本在 `scripts/`，如 `start_dev.sh` 一键启动全栈。

## 关键开发流程
- **一键启动开发环境**：`./scripts/start_dev.sh`（推荐，自动启动 FastAPI + Next.js）
- **后端独立启动**：`./scripts/start_api.sh` 或 `uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`
- **前端独立启动**：`cd web && npm install && npm run dev`
- **API 文档**：`http://localhost:8000/docs`（Swagger UI）
- **前端界面**：`http://localhost:3000`（Next.js Web Dashboard）

## 数据与集成约定
- **API 设计**：所有数据通过 RESTful API 提供，端点如 `/api/price`、`/api/attention`、`/api/news`，详见 `src/api/main.py` 和 `web/lib/api.ts`。
- **环境变量**：API 密钥等敏感信息通过 `.env` 文件注入，参考 `cp .env.example .env`。
- **Mock/真实数据切换**：删除 `data/raw/attention_zec_news.csv` 后自动拉取真实数据。
- **前后端解耦**：前端通过 `NEXT_PUBLIC_API_BASE_URL` 环境变量配置后端地址。

## 项目特有约定与模式
- **数据自动检测与拉取**：缺失数据时后端自动抓取并存储。
- **API 客户端统一封装**：前端所有数据请求通过 `web/lib/api.ts`，便于切换 mock/真实数据。
- **多时间周期支持**：价格与注意力分数均支持 1D/4H/1H/15M 等多周期。
- **代理支持**：后端支持 HTTP/SOCKS5 代理，见 `requests` 配置。

## 常见问题与调试
- **端口冲突**：前端 3000/3001，后端 8000。
- **依赖安装**：后端 `pip install -r requirements.txt`，前端 `cd web && npm install`。
- **数据缺失**：优先检查 `data/raw/` 是否有 mock 数据残留，或运行后台服务自动获取。

## 参考文件
- `README.md`（本目录与 web/）
- `WEB_OVERVIEW.md`（前端集成与架构）
- `src/api/main.py`（API 端点实现）
- `web/lib/api.ts`（前端 API 客户端）
- `scripts/start_dev.sh`（一键启动脚本）

---
如需扩展新 API、特征或前端页面，请遵循现有目录结构与接口风格。遇到不明确的约定或流程，请优先查阅上述文档或现有实现。