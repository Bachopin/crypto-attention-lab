#!/bin/bash

# Crypto Attention Lab - 停止所有服务
# 等同于 stop_all.sh

cd "$(dirname "$0")/.."

echo "🛑 停止 Crypto Attention Lab 服务..."
echo ""

# 停止后端
echo "📡 停止后端 API..."
pkill -9 -f "uvicorn.*src.api.main" 2>/dev/null && echo "✅ 后端已停止" || echo "ℹ️  后端未运行"
pkill -9 -f "python.*src.api" 2>/dev/null || true

# 停止前端
echo "🌐 停止前端服务..."
pkill -9 -f "next dev" 2>/dev/null && echo "✅ 前端已停止" || echo "ℹ️  前端未运行"
pkill -9 -f "next-server" 2>/dev/null || true
pkill -9 -f "node.*next" 2>/dev/null || true
pkill -9 -f "node.*turbopack" 2>/dev/null || true

# 清理端口
echo "🔌 清理端口..."
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

sleep 1

echo ""
echo "✨ 所有服务已停止"
echo ""
