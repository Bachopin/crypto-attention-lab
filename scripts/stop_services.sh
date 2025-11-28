#!/bin/bash

# Crypto Attention Lab - 停止所有服务

echo "🛑 停止 Crypto Attention Lab 服务..."

# 停止后端
if pgrep -f "uvicorn src.api.main" > /dev/null; then
    echo "📡 停止后端 API..."
    pkill -f "uvicorn src.api.main"
    echo "✅ 后端已停止"
else
    echo "ℹ️  后端未运行"
fi

# 停止前端
if pgrep -f "next dev" > /dev/null; then
    echo "🌐 停止前端服务..."
    pkill -f "next dev"
    echo "✅ 前端已停止"
else
    echo "ℹ️  前端未运行"
fi

echo ""
echo "✨ 所有服务已停止"
