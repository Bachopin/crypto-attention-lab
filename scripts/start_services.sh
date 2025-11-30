#!/bin/bash

# Crypto Attention Lab - 启动前后端服务（后台模式）
# 服务以后台方式运行，日志输出到 logs/ 目录

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 设置 NO_PROXY 避免本地通信走代理
export NO_PROXY="localhost,127.0.0.1,0.0.0.0,host.docker.internal,*.local"
export no_proxy="$NO_PROXY"

# 创建日志目录
mkdir -p logs

echo "🚀 启动 Crypto Attention Lab 服务..."
echo ""

BACKOFF_RETRIES=15
BACKOFF_DELAY=2

# ========================================
# 第一步：彻底清理所有现有服务
# ========================================
echo "🧹 彻底清理所有旧服务..."

# 停止后端进程 (Safer kill)
ps aux | grep "uvicorn.*src.api.main" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "python.*src.api" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true

# 停止前端进程 (Safer kill)
ps aux | grep "next dev" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "next-server" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "node.*next" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "node.*turbopack" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true

# 强制释放端口
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

sleep 1
echo "✅ 所有旧服务已清理"
echo ""

# ========================================
# 启动后端 API
# ========================================
echo "📡 启动后端 API (端口 8000)..."
nohup uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload > logs/api.log 2>&1 &
BACKEND_PID=$!

BACKEND_READY=false
for ((i=1; i<=BACKOFF_RETRIES; i++)); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        BACKEND_READY=true
        break
    fi
    sleep "$BACKOFF_DELAY"
done

if [ "$BACKEND_READY" = true ]; then
    echo "✅ 后端 API 启动成功 (PID: $BACKEND_PID)"
else
    echo "❌ 后端 API 启动失败，请查看 logs/api.log"
    exit 1
fi

# ========================================
# 启动前端 (Turbopack 已在 package.json 配置)
# ========================================
echo "🌐 启动前端 Next.js (Turbopack, 端口 3000)..."
cd web
PORT=3000 nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

FRONTEND_READY=false
for ((i=1; i<=BACKOFF_RETRIES; i++)); do
    STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null)
    if [ "$STATUS_CODE" = "200" ] || [ "$STATUS_CODE" = "302" ] || [ "$STATUS_CODE" = "307" ]; then
        FRONTEND_READY=true
        break
    fi
    sleep "$BACKOFF_DELAY"
done

if [ "$FRONTEND_READY" = true ]; then
    echo "✅ 前端服务启动成功 (PID: $FRONTEND_PID)"
else
    echo "❌ 前端服务启动失败，请查看 logs/frontend.log"
    exit 1
fi

echo ""
echo "✨ 所有服务启动完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📱 前端界面:    http://localhost:3000"
echo "🔌 API 文档:    http://localhost:8000/docs"
echo "💓 健康检查:    http://localhost:8000/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 查看日志:"
echo "   后端: tail -f logs/api.log"
echo "   前端: tail -f logs/frontend.log"
echo ""
echo "🛑 停止服务: ./scripts/stop_all.sh"
echo ""
