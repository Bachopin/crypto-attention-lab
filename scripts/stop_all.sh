#!/bin/bash

# Crypto Attention Lab - 停止所有服务

cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}停止 Crypto Attention Lab 服务${NC}"
echo -e "${RED}========================================${NC}"
echo ""

echo "停止 FastAPI 后端..."
pkill -f "uvicorn.*src.api.main:app" 2>/dev/null && echo -e "${GREEN}✓ 后端已停止${NC}" || echo "后端未运行"

echo "停止 Next.js 前端..."
pkill -f "next dev" 2>/dev/null && echo -e "${GREEN}✓ 前端已停止${NC}" || echo "前端未运行"

# 清理端口占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "清理端口 8000..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi

if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "清理端口 3000..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}✓ 所有服务已停止${NC}"
echo ""
