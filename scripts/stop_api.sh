#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f server.pid ]; then
  PID=$(cat server.pid)
  if ps -p "$PID" > /dev/null 2>&1; then
    echo "Stopping API server PID $PID";
    kill "$PID";
    sleep 1;
  else
    echo "Process $PID not running";
  fi
  rm -f server.pid
  echo "API server stopped"
else
  echo "server.pid not found (already stopped?)"
fi
