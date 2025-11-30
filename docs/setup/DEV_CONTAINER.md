# Dev Container 使用指南

## 🌐 访问服务

### 在 VS Code 中访问

1. **查看端口转发**
   - 点击 VS Code 底部的 **"端口"** 标签（Ports）
   - 你会看到已转发的端口列表

2. **打开服务**
   - **前端界面** (3000) - 点击 "在浏览器中打开" 图标 🌐
   - **后端 API** (8000) - 点击 "在浏览器中打开" 图标 🌐
   - **API 文档** - 访问后端 URL 后加上 `/docs`

### 端口说明

| 端口 | 服务 | 描述 |
|------|------|------|
| 3000 | Frontend (Next.js) | 前端 Web 界面 |
| 8000 | Backend API (FastAPI) | 后端 RESTful API |

## 🚀 启动/停止服务

### 快速启动（推荐）

```bash
./scripts/start_services.sh
```

此脚本会：
- ✅ 自动停止旧进程
- ✅ 启动后端 API (端口 8000)
- ✅ 启动前端服务 (端口 3000)
- ✅ 验证服务健康状态
- ✅ 日志输出到 `logs/` 目录

> ⚙️ `start_services.sh` 在脚本顶部定义了 `BACKOFF_RETRIES`/`BACKOFF_DELAY`（默认为 10 次、3 秒间隔），你可以根据 Dev Container 的性能调整这些值来给后端/前端更多预热时间。

### 停止服务

```bash
./scripts/stop_services.sh
```

### 查看日志

```bash
# 后端日志
tail -f logs/api.log

# 前端日志
tail -f logs/frontend.log
```

## 📋 服务验证

### 检查服务状态

```bash
# 后端健康检查
curl http://localhost:8000/health

# 前端状态检查
curl -I http://localhost:3000
```

### 查看运行进程

```bash
ps aux | grep -E "(uvicorn|next)" | grep -v grep
```

## 🔧 Dev Container 配置

配置文件: `.devcontainer/devcontainer.json`

### VS Code 扩展

本开发容器已预装以下扩展，开箱即用：

- Python: `ms-python.python`、`ms-python.vscode-pylance`
- 前端工具: `dbaeumer.vscode-eslint`、`esbenp.prettier-vscode`
- AI 辅助: `github.copilot`、`github.copilot-chat`

如需禁用 Copilot，可在 VS Code 命令面板输入“Copilot: Disable”暂时关闭。

### 端口转发配置

```jsonc
"forwardPorts": [3000, 8000],

"portsAttributes": {
  "3000": {
    "label": "Frontend (Next.js)",
    "onAutoForward": "notify"
  },
  "8000": {
    "label": "Backend API (FastAPI)",
    "onAutoForward": "notify"
  }
}
```

### 特性
- ✅ 自动端口转发
- ✅ 端口标签显示
- ✅ 自动通知（前端和后端）
- ✅ Python 3.11 + Node.js 20
- ✅ 依赖自动安装

## 🌍 外部访问

如果你使用的是 GitHub Codespaces 或类似服务：

1. 端口会自动暴露为公开 URL
2. 在 "端口" 面板中，右键点击端口 → "端口可见性" → "公开"
3. 复制自动生成的 URL（格式类似 `https://xxx-3000.preview.app.github.dev`）

## 📝 常见问题

### Q: 端口被占用怎么办？
```bash
# 查看占用端口的进程
lsof -i :3000
lsof -i :8000

# 停止所有服务
./scripts/stop_services.sh
```

### Q: 服务启动失败？
```bash
# 查看日志
tail -50 logs/api.log
tail -50 logs/frontend.log

# 手动重启
./scripts/stop_services.sh
./scripts/start_services.sh
```

### Q: 看不到端口面板？
- 按 `Ctrl + J` (Windows/Linux) 或 `Cmd + J` (Mac) 打开面板
- 选择 "端口" 标签

## 🎯 快速链接

启动服务后，你可以直接访问：

- 🌐 **前端**: `http://localhost:3000`
- 📡 **API 文档**: `http://localhost:8000/docs`
- 💓 **健康检查**: `http://localhost:8000/health`
- 📊 **API 根路径**: `http://localhost:8000/`

---

💡 **提示**: 所有服务都配置为后台运行，重启 Dev Container 后需要重新运行 `./scripts/start_services.sh`
