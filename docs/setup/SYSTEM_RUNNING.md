# 系统运行指南 (System Running)

本文档详细介绍了 Crypto Attention Lab 的多种运行模式与运维操作。

## 运行模式

### 1. 全栈开发模式 (Full Stack Dev)
最常用的开发模式，同时启动前后端，并开启热重载 (Hot Reload)。
```bash
./scripts/dev.sh
```

### 2. 仅后端模式 (Backend Only)
如果你只需要开发 API 或运行数据脚本：
```bash
./scripts/api.sh
# 或者直接使用 uvicorn
PYTHONPATH=$(pwd) uvicorn src.api.main:app --app-dir "$(pwd)" --reload --host 0.0.0.0 --port 8000
```

### 3. 仅前端模式 (Frontend Only)
如果你只需要开发 UI，且后端已经在运行 (或使用 Mock 数据)：
```bash
./scripts/web.sh
# 或者
cd web && npm run dev
```

## 后台任务与数据流

系统启动后，FastAPI 会自动管理以下后台任务（频率可通过 `.env` 覆盖）：
- **价格轮询**: 每 10 分钟（`PRICE_UPDATE_INTERVAL=600`）从 Binance 拉取最新价格。
- **新闻聚合**: 每 1 小时（`NEWS_UPDATE_INTERVAL=3600`）检查新闻源更新。
- **注意力特征**: 冷却期 1 小时（`FEATURE_UPDATE_COOLDOWN=3600`）后增量更新。
- **Google Trends**: 冷却期 12 小时（`GOOGLE_TRENDS_COOLDOWN=43200`）。
- **WebSocket 推送**: 当数据更新时，自动通过 WebSocket 推送给前端。

> 详细更新链路见 [AUTO_UPDATE_PIPELINE.md](../backend/AUTO_UPDATE_PIPELINE.md)。

## 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Frontend | 3000 | Next.js Web 界面 |
| Backend | 8000 | FastAPI 接口与 Swagger 文档 |
| WebSocket | 8000 | `/ws/price`, `/ws/attention` |

## 停止服务

- **前台运行**: 在终端按 `Ctrl+C`。`dev.sh` 会自动捕获信号并关闭所有子进程。
- **后台运行**: 如果服务在后台运行，可以使用：
```bash
./scripts/stop.sh
```
或者手动清理：
```bash
pkill -f "uvicorn"
pkill -f "next-server"
```

## 故障排除
### 后端启动报 `ModuleNotFoundError: No module named 'src'`

原因：当前工作目录不在项目根，或 Python 路径未包含项目根。

解决：
```bash
export PYTHONPATH=$(pwd)
uvicorn src.api.main:app --app-dir "$(pwd)" --reload --host 0.0.0.0 --port 8000
```
或使用脚本：`./scripts/api.sh`、`./scripts/dev.sh`（已内置修复）。

### 1. 端口被占用
错误信息: `Address already in use`
解决:
```bash
lsof -ti:8000 | xargs kill -9
lsof -ti:3000 | xargs kill -9
```

### 2. 数据库锁定
错误信息: `database is locked`
解决: 
- 确保没有其他进程正在写入 SQLite 数据库。
- 检查是否有僵尸 Python 进程：`ps aux | grep python`。

### 3. 前端连接失败
错误信息: `Connection refused` (在浏览器控制台)
解决:
- 检查后端是否启动: `curl http://localhost:8000/health`
- 检查前端 `.env.local` 中的 `NEXT_PUBLIC_API_BASE_URL` 是否正确配置。
