#!/bin/bash

# Crypto Attention Lab - 停止 API 服务器

cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}停止 API 服务器...${NC}"
echo ""

# 停止 uvicorn 进程
pkill -9 -f "uvicorn.*src.api.main" 2>/dev/null && echo -e "${GREEN}✓ uvicorn 已停止${NC}" || echo "• uvicorn 未运行"
pkill -9 -f "python.*src.api" 2>/dev/null || true

# 清理端口 8000
if lsof -ti:8000 >/dev/null 2>&1; then
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✓ 端口 8000 已释放${NC}"
else
    echo "• 端口 8000 未占用"
fi

echo ""
echo -e "${GREEN}✓ API 服务器已停止${NC}"
