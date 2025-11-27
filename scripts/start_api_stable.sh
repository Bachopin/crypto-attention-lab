#!/usr/bin/env bash
# Stable (no auto-reload) FastAPI startup with log rotation friendly output
set -euo pipefail
cd "$(dirname "$0")/.."
LOG_FILE="fastapi.log"
PYTHON_BIN="/Users/mextrel/VSCode/.venv/bin/python"
APP="src.api.main:app"
HOST="0.0.0.0"
PORT="8000"
if [ -f server.pid ]; then
  PID=$(cat server.pid)
  if ps -p "$PID" > /dev/null 2>&1; then
    echo "Server already running (PID $PID). Use scripts/stop_api.sh first.";
    exit 0;
  else
    rm -f server.pid
  fi
fi
echo "Starting FastAPI (stable) on http://$HOST:$PORT";
nohup "$PYTHON_BIN" -m uvicorn "$APP" --host "$HOST" --port "$PORT" --log-level info --access-log >> "$LOG_FILE" 2>&1 &
echo $! > server.pid
sleep 2
if curl -m 3 -sS "http://127.0.0.1:$PORT/health" | grep -q '"healthy"'; then
  echo "Health check OK";
else
  echo "Health check FAILED";
fi
