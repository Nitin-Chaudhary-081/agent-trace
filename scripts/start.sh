#!/usr/bin/env bash
# Start the AgentTrace stack: Flask API (8000) + Next.js observer (3001).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "No .env found; copying template. Fill it in and restart to enable live tools."
  cp .env.example .env
fi

PY="${PY:-/data/data/com.termux/files/usr/bin/python3}"
export PYTHONPATH="$ROOT:$ROOT/api:$ROOT/api/src:$ROOT/agent${PYTHONPATH:+:$PYTHONPATH}"

echo "Starting AgentTrace API on :8000 ..."
FLASK_APP=src/app.py "$PY" -m flask run --host=0.0.0.0 --port=8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT

echo "Starting observer UI on :3001 ..."
(cd web && npx next dev --port 3001) &
UI_PID=$!
trap 'kill $API_PID $UI_PID 2>/dev/null || true' EXIT

echo "API:  http://localhost:8000/health"
echo "UI:   http://localhost:3001"
wait