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
ps aux | grep "uvicorn.*src.api.main" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9
ps aux | grep "python.*src.api" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9

# 2. 停止前端进程
echo -e "${YELLOW}[2/4] 停止前端进程...${NC}"
# 排除 VS Code Server 进程，防止误杀
ps aux | grep "next dev" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9
ps aux | grep "next-server" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9
# node.*next 这种匹配太宽泛，容易误杀 VS Code 插件，改用更精确的匹配或仅依赖端口清理
# 如果必须杀 node 进程，务必排除 .vscode-server
ps aux | grep "node" | grep "next" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9

# 3. 清理端口 8000
echo -e "${YELLOW}[3/4] 清理端口 8000...${NC}"
if lsof -ti:8000 >/dev/null 2>&1; then
    PIDS=$(lsof -ti:8000)
    for pid in $PIDS; do
        if ! ps -p $pid -o args= | grep -q ".vscode-server"; then
            kill -9 $pid 2>/dev/null
        fi
    done
    echo -e "${GREEN}✓ 端口 8000 已释放${NC}"
else
    echo "• 端口 8000 未占用"
fi

# 4. 清理端口 3000
echo -e "${YELLOW}[4/4] 清理端口 3000...${NC}"
if lsof -ti:3000 >/dev/null 2>&1; then
    PIDS=$(lsof -ti:3000)
    for pid in $PIDS; do
        if ! ps -p $pid -o args= | grep -q ".vscode-server"; then
            kill -9 $pid 2>/dev/null
        fi
    done
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
