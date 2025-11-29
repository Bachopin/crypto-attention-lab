#!/bin/bash

# Crypto Attention Lab - 全栈开发模式启动脚本（前台模式）
# 按 Ctrl+C 同时停止所有服务
# Usage: ./scripts/start_dev.sh

# Change to project root directory
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 设置 NO_PROXY 避免本地通信走代理
export NO_PROXY="localhost,127.0.0.1,0.0.0.0,host.docker.internal,*.local"
export no_proxy="$NO_PROXY"

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Crypto Attention Lab - Full Stack Dev${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ========================================
# 第一步：彻底清理所有现有服务
# ========================================
echo -e "${YELLOW}[清理] 彻底停止所有旧服务...${NC}"

# 停止后端进程
pkill -9 -f "uvicorn.*src.api.main" 2>/dev/null || true
pkill -9 -f "python.*src.api" 2>/dev/null || true

# 停止前端进程
pkill -9 -f "next dev" 2>/dev/null || true
pkill -9 -f "next-server" 2>/dev/null || true
pkill -9 -f "node.*next" 2>/dev/null || true
pkill -9 -f "node.*turbopack" 2>/dev/null || true

# 强制释放端口
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

sleep 1
echo -e "${GREEN}✓ 所有旧服务已清理${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${RED}正在停止所有服务...${NC}"
    pkill -9 -f "uvicorn.*src.api.main" 2>/dev/null || true
    pkill -9 -f "next dev" 2>/dev/null || true
    pkill -9 -f "node.*next" 2>/dev/null || true
    lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
    echo -e "${GREEN}✓ 所有服务已停止${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start FastAPI backend in background
echo -e "${GREEN}[1/2] 启动 FastAPI 后端...${NC}"
uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${YELLOW}      等待后端启动...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}      ✓ 后端启动成功 (PID: $BACKEND_PID)${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}      ✗ 后端启动超时${NC}"
        cleanup
        exit 1
    fi
    sleep 1
done

# Start Next.js frontend (npm run dev already includes --turbopack)
echo -e "${GREEN}[2/2] 启动 Next.js 前端 (Turbopack)...${NC}"
cd web
PORT=3000 npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 开发服务器运行中${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  后端 API:  ${BLUE}http://localhost:8000${NC}"
echo -e "  API 文档:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  前端界面:  ${BLUE}http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# Wait for all background processes
wait
