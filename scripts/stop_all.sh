#!/bin/bash

# Crypto Attention Lab - 停止所有服务
# 彻底清理所有相关进程和端口

cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}停止 Crypto Attention Lab 服务${NC}"
echo -e "${RED}========================================${NC}"
echo ""

# 1. 停止后端进程
echo -e "${YELLOW}[1/4] 停止后端进程...${NC}"
pkill -9 -f "uvicorn.*src.api.main" 2>/dev/null && echo -e "${GREEN}✓ uvicorn 已停止${NC}" || echo "• uvicorn 未运行"
pkill -9 -f "python.*src.api" 2>/dev/null || true

# 2. 停止前端进程
echo -e "${YELLOW}[2/4] 停止前端进程...${NC}"
pkill -9 -f "next dev" 2>/dev/null && echo -e "${GREEN}✓ next dev 已停止${NC}" || echo "• next dev 未运行"
pkill -9 -f "next-server" 2>/dev/null || true
pkill -9 -f "node.*next" 2>/dev/null || true
pkill -9 -f "node.*turbopack" 2>/dev/null || true

# 3. 清理端口 8000
echo -e "${YELLOW}[3/4] 清理端口 8000...${NC}"
if lsof -ti:8000 >/dev/null 2>&1; then
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✓ 端口 8000 已释放${NC}"
else
    echo "• 端口 8000 未占用"
fi

# 4. 清理端口 3000
echo -e "${YELLOW}[4/4] 清理端口 3000...${NC}"
if lsof -ti:3000 >/dev/null 2>&1; then
    lsof -ti:3000 | xargs kill -9 2>/dev/null
    echo -e "${GREEN}✓ 端口 3000 已释放${NC}"
else
    echo "• 端口 3000 未占用"
fi

sleep 1

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 所有服务已停止${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
