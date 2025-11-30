#!/bin/bash

# Crypto Attention Lab - 停止所有服务
# 等同于 stop_all.sh

cd "$(dirname "$0")/.."

echo "🛑 停止 Crypto Attention Lab 服务..."
echo ""

# 停止后端
echo "📡 停止后端 API..."
ps aux | grep "uvicorn.*src.api.main" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9
ps aux | grep "python.*src.api" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9

# 停止前端
echo "🌐 停止前端服务..."
ps aux | grep "next dev" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9
ps aux | grep "next-server" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9
ps aux | grep "node" | grep "next" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9

# 清理端口
echo "🔌 清理端口..."
if lsof -ti:8000 >/dev/null 2>&1; then
    PIDS=$(lsof -ti:8000)
    for pid in $PIDS; do
        if ! ps -p $pid -o args= | grep -q ".vscode-server"; then
            kill -9 $pid 2>/dev/null
        fi
    done
fi

if lsof -ti:3000 >/dev/null 2>&1; then
    PIDS=$(lsof -ti:3000)
    for pid in $PIDS; do
        if ! ps -p $pid -o args= | grep -q ".vscode-server"; then
            kill -9 $pid 2>/dev/null
        fi
    done
fi

sleep 1

echo ""
echo "✨ 所有服务已停止"
echo ""
