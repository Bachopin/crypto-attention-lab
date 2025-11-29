#!/bin/bash

# Crypto Attention Lab - 启动前后端服务（Dev Container 专用）
# 服务以后台方式运行，日志输出到 logs/ 目录

cd "$(dirname "$0")/.."

# 创建日志目录
mkdir -p logs

echo "🚀 启动 Crypto Attention Lab 服务..."
BACKOFF_RETRIES=10
BACKOFF_DELAY=3

# 检查并停止已有进程
if pgrep -f "uvicorn src.api.main" > /dev/null; then
    echo "⚠️  停止现有后端服务..."
    pkill -f "uvicorn src.api.main"
    sleep 1
fi

if pgrep -f "next dev" > /dev/null; then
    echo "⚠️  停止现有前端服务..."
    pkill -f "next dev"
    sleep 1
fi

# 启动后端 API
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

# 启动前端 (使用 Turbopack 加速开发，已在 package.json 配置)
echo "🌐 启动前端 Next.js (Turbopack, 端口 3000)..."
cd web
nohup npm run dev -- -p 3000 > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
FRONTEND_READY=false
for ((i=1; i<=BACKOFF_RETRIES; i++)); do
    STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000)
    if [ "$STATUS_CODE" = "200" ] || [ "$STATUS_CODE" = "302" ]; then
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
echo "🛑 停止服务: ./scripts/stop_services.sh"
echo ""
