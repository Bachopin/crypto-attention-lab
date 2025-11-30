#!/bin/bash

# Crypto Attention Lab - FastAPI 后端启动脚本
# Usage: ./scripts/start_api.sh

# Change to project root directory
cd "$(dirname "$0")/.."

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Crypto Attention Lab - 启动后端 API${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ========================================
# 第一步：彻底清理旧的后端服务
# ========================================
echo -e "${YELLOW}[清理] 停止旧的后端服务...${NC}"

# Safer kill: exclude .vscode-server processes
ps aux | grep "uvicorn.*src.api.main" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "python.*src.api" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true

lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1
echo -e "${GREEN}✓ 端口 8000 已释放${NC}"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "激活虚拟环境..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "激活虚拟环境..."
    source .venv/bin/activate
fi

# Check if FastAPI is installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}未找到 FastAPI，正在安装依赖...${NC}"
    pip install -r requirements.txt
fi

echo -e "${GREEN}[启动] FastAPI 后端${NC}"
echo ""
echo -e "  API 地址:  ${BLUE}http://localhost:8000${NC}"
echo -e "  API 文档:  ${BLUE}http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"
echo ""

uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
