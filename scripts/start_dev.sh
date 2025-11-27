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

# Start FastAPI backend in background
echo -e "${GREEN}[1/2] Starting FastAPI backend...${NC}"
./scripts/start_api.sh &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start Next.js frontend
echo -e "${GREEN}[2/2] Starting Next.js frontend...${NC}"
cd web
npm run dev &
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
