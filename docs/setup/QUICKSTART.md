# 快速开始指南 (Quickstart)

## 1. 环境准备

### 必需组件
- **Python 3.10+**: 后端运行环境
- **Node.js 18+**: 前端运行环境
- **Git**: 代码版本控制

### 可选组件
- **Docker**: 如果使用 Dev Container 开发
- **Make**: 如果使用 Makefile (本项目主要使用 shell 脚本)

## 2. 安装依赖

### 后端依赖
```bash
# 创建虚拟环境 (推荐)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 开发依赖
```

### 前端依赖
```bash
cd web
npm install
# 或者使用 yarn / pnpm
# yarn install
# pnpm install
```

## 3. 配置环境变量

复制示例配置文件：
```bash
cp .env.example .env
cp web/.env.example web/.env.local
```
默认配置通常可以直接运行。如果需要真实数据，请在 `.env` 中填入 API Key (如 NewsAPI, Binace API 等)。

推荐关键变量：
- `FEATURE_CACHE_TTL`（后端）: 预计算特征热缓存 TTL（秒），默认 `60`。增大可减少重复查询频率，减小可提高新数据可见性。
- `NEXT_PUBLIC_API_BASE_URL`（前端）: 覆盖前端调用的 API 根地址（默认使用 Next.js rewrites 代理至 `http://127.0.0.1:8000`）。部署到远端时设置为后端外网地址。

## 4. 启动应用

### 一键启动 (推荐)
```bash
./scripts/dev.sh
```
此脚本会自动：
1. 检查端口占用
2. 启动 FastAPI 后端 (Port 8000)
3. 启动 Next.js 前端 (Port 3000)
4. 实时显示日志

### 验证运行
- 打开浏览器访问 [http://localhost:3000](http://localhost:3000)
- 查看 API 文档 [http://localhost:8000/docs](http://localhost:8000/docs)

### 仅后端快速启动（可选）
如果你只想启动后端：
```bash
./scripts/api.sh
```
或者手动（确保加入项目根路径以避免 `ModuleNotFoundError: src`）：
```bash
PYTHONPATH=$(pwd) uvicorn src.api.main:app \
	--app-dir "$(pwd)" \
	--reload \
	--host 0.0.0.0 \
	--port 8000
```

## 5. 常见问题

- **端口冲突**: 确保 3000 和 8000 端口未被占用。
- **依赖报错**: 尝试删除 `.venv` 或 `node_modules` 重新安装。
- **权限问题**: 运行脚本时如果提示 `Permission denied`，请执行 `chmod +x scripts/*.sh`。
