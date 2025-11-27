#!/bin/bash

# Crypto Attention Lab - FastAPI Backend Startup Script
# Usage: ./scripts/start_api.sh

# Change to project root directory
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if FastAPI is installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Error: FastAPI not found. Installing dependencies..."
    pip install -r requirements.txt
fi

# Start FastAPI server
echo "Starting FastAPI backend on http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo "Press Ctrl+C to stop the server"
echo ""
# Free the port 8000 if occupied
if lsof -ti tcp:8000 >/dev/null 2>&1; then
    echo "Port 8000 is in use. Freeing it..."
    lsof -ti tcp:8000 | xargs -r kill -9
    sleep 1
fi

uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
