#!/bin/bash

# Crypto Attention Lab - 快速启动脚本
# 自动清理旧进程并启动前后端服务

set -e

# 切换到项目根目录
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# 设置 NO_PROXY 避免本地通信走代理
export NO_PROXY="localhost,127.0.0.1,0.0.0.0,host.docker.internal,*.local"
export no_proxy="$NO_PROXY"

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Crypto Attention Lab - 启动服务${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ========================================
# 第一步：彻底清理所有现有服务
# ========================================
echo -e "${YELLOW}[清理] 彻底停止所有旧服务...${NC}"

# 停止后端进程 (Safer kill)
ps aux | grep "uvicorn.*src.api.main" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "python.*src.api" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true

# 停止前端进程 (Safer kill)
ps aux | grep "next dev" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "next-server" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "node.*next" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true
ps aux | grep "node.*turbopack" | grep -v grep | grep -v .vscode-server | awk '{print $2}' | xargs -r kill -9 2>/dev/null || true

# 强制释放端口
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

sleep 1
echo -e "${GREEN}✓ 所有旧服务已清理${NC}"
echo ""

# 启动后端
echo -e "${GREEN}[1/2] 启动 FastAPI 后端...${NC}"
uvicorn src.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    > /tmp/fastapi.log 2>&1 &

BACKEND_PID=$!
echo "      后端 PID: $BACKEND_PID"

# 等待后端启动
echo -e "${YELLOW}      等待后端启动...${NC}"
for i in {1..10}; do
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}      ✓ 后端启动成功${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${YELLOW}      ✗ 后端启动超时，请查看日志: tail -f /tmp/fastapi.log${NC}"
        exit 1
    fi
    sleep 1
done

# 启动前端 (使用 Turbopack 加速开发，已在 package.json 配置)
echo -e "${GREEN}[2/2] 启动 Next.js 前端 (Turbopack)...${NC}"
cd web
PORT=3000 npm run dev > /tmp/nextjs.log 2>&1 &
FRONTEND_PID=$!
echo "      前端 PID: $FRONTEND_PID"

# 等待前端启动
echo -e "${YELLOW}      等待前端启动...${NC}"
cd ..
for i in {1..15}; do
    if curl -s http://localhost:3000 >/dev/null 2>&1; then
        echo -e "${GREEN}      ✓ 前端启动成功${NC}"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "${YELLOW}      ✗ 前端启动超时，请查看日志: tail -f /tmp/nextjs.log${NC}"
        exit 1
    fi
    sleep 1
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ 服务启动成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e ""
echo -e "  后端 API:  ${BLUE}http://localhost:8000${NC}"
echo -e "  API 文档:  ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  前端界面:  ${BLUE}http://localhost:3000${NC}"
echo -e ""
echo -e "  后端日志:  tail -f /tmp/fastapi.log"
echo -e "  前端日志:  tail -f /tmp/nextjs.log"
echo -e ""
echo -e "${YELLOW}提示: 服务在后台运行${NC}"
echo -e "${YELLOW}停止服务: ./scripts/stop_all.sh${NC}"
echo ""
