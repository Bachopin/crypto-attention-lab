#!/bin/bash

# Crypto Attention Lab - 稳定模式启动后端（无 hot-reload）
# 用于生产环境或需要稳定运行的场景

cd "$(dirname "$0")/.."

# 创建日志目录
mkdir -p logs

LOG_FILE="logs/api.log"
HOST="0.0.0.0"
PORT="8000"

echo "🚀 启动 FastAPI 后端 (稳定模式)..."
echo ""

# 彻底清理旧进程
echo "🧹 清理旧进程..."
pkill -9 -f "uvicorn.*src.api.main" 2>/dev/null || true
pkill -9 -f "python.*src.api" 2>/dev/null || true
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1
echo "✅ 旧进程已清理"
echo ""

# 启动服务
echo "📡 启动 FastAPI on http://$HOST:$PORT"
nohup uvicorn src.api.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level info \
    --access-log >> "$LOG_FILE" 2>&1 &

BACKEND_PID=$!
sleep 2

# 健康检查
if curl -s http://localhost:$PORT/health | grep -q '"status"'; then
    echo "✅ 健康检查通过 (PID: $BACKEND_PID)"
else
    echo "❌ 健康检查失败，请查看 $LOG_FILE"
    exit 1
fi

echo ""
echo "✨ 后端启动完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔌 API 地址:    http://localhost:$PORT"
echo "📖 API 文档:    http://localhost:$PORT/docs"
echo "📋 日志文件:    $LOG_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
