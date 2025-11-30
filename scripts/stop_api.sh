#!/bin/bash

# Crypto Attention Lab - 停止 API 服务器

cd "$(dirname "$0")/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}停止 API 服务器...${NC}"
echo ""

# 停止 uvicorn 进程
# 使用更精确的匹配，并排除 VS Code Server 相关进程
echo "正在停止 uvicorn..."
ps aux | grep "uvicorn.*src.api.main" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9

echo "正在停止 python api..."
ps aux | grep "python.*src.api" | grep -v "grep" | grep -v ".vscode-server" | awk '{print $2}' | xargs -r kill -9

# 清理端口 8000
if lsof -ti:8000 >/dev/null 2>&1; then
    # 排除 VS Code 进程占用（虽然通常 VS Code 不会直接占用 8000，但以防万一）
    PIDS=$(lsof -ti:8000)
    for pid in $PIDS; do
        # 检查该 PID 是否属于 VS Code
        if ! ps -p $pid -o args= | grep -q ".vscode-server"; then
            kill -9 $pid 2>/dev/null
        fi
    done
    echo -e "${GREEN}✓ 端口 8000 已释放${NC}"
else
    echo "• 端口 8000 未占用"
fi

echo ""
echo -e "${GREEN}✓ API 服务器已停止${NC}"
