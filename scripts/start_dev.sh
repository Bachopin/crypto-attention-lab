#!/bin/bash

# Crypto Attention Lab - Full Stack Development Startup Script
# Usage: ./scripts/start_dev.sh

# Change to project root directory
cd "$(dirname "$0")/.."

# Colors for terminal output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Crypto Attention Lab - Full Stack Dev${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${BLUE}Shutting down servers...${NC}"
    kill 0
    exit
}

trap cleanup SIGINT SIGTERM

# Start FastAPI backend in background (ensure port 8000)
echo -e "${GREEN}[1/2] Starting FastAPI backend...${NC}"
./scripts/start_api.sh &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start Next.js frontend on fixed port 3000 (free if occupied)
# Note: npm run dev already includes --turbopack (see package.json)
echo -e "${GREEN}[2/2] Starting Next.js frontend (Turbopack)...${NC}"
cd web
if lsof -ti tcp:3000 >/dev/null 2>&1; then
    echo "Port 3000 is in use. Freeing it..."
    lsof -ti tcp:3000 | xargs -r kill -9
    sleep 1
fi
npm run dev -- -p 3000 &
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Development servers running${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "FastAPI:  http://localhost:8000"
echo -e "Docs:     http://localhost:8000/docs"
echo -e "Frontend: http://localhost:3000"
echo -e ""
echo -e "Press Ctrl+C to stop all servers"
echo ""

# Wait for all background processes
wait
