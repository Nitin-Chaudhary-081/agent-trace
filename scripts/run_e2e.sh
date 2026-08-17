#!/usr/bin/env bash
# Offline-first end-to-end smoke test for AgentTrace.
# 1. Boots the API on an isolated DB + memory file.
# 2. Submits a data_lookup_report task.
# 3. Polls until the run settles, asserts it reaches COMPLETED with score >= 80.
# 4. Verifies the security-attack endpoint returns cached results.
#
# Uses the real .env when present (live creds) and degrades gracefully without it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PY:-/data/data/com.termux/files/usr/bin/python3}"
export PYTHONPATH="$ROOT:$ROOT/api:$ROOT/api/src:$ROOT/agent${PYTHONPATH:+:$PYTHONPATH}"

PORT="${AGENTTRACE_E2E_PORT:-8000}"
DB="$(mktemp /tmp/agenttrace_e2e_XXXX.sqlite)"
MEM="$(mktemp /tmp/agenttrace_e2e_MEMORY_XXXX.md)"
LOG="$(mktemp /tmp/agenttrace_e2e_api_XXXX.log)"

echo "Booting API on :$PORT (db=$DB)"
AGENTTRACE_DB_PATH="$DB" AGENTTRACE_MEMORY_PATH="$MEM" \
  setsid nohup "$PY" -m flask --app src/app.py run --port "$PORT" \
  > "$LOG" 2>&1 < /dev/null &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true; rm -f "$DB" "$MEM" "$LOG"' EXIT

for i in $(seq 1 30); do
  if curl -sf -m 2 "http://127.0.0.1:$PORT/health" > /dev/null; then break; fi
  sleep 1
done

echo "Submitting data_lookup_report task"
RUN_ID=$(curl -sf -X POST "http://127.0.0.1:$PORT/api/v1/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"task":"lookup records from table","task_type":"data_lookup_report"}' \
  | "$PY" -c "import json,sys; print(json.load(sys.stdin)['run_id'])")

STATUS=""
for i in $(seq 1 60); do
  STATUS=$(curl -sf "http://127.0.0.1:$PORT/api/v1/runs/$RUN_ID" \
    | "$PY" -c "import json,sys; print(json.load(sys.stdin)['run']['status'])" || echo "")
  if [ "$STATUS" = "COMPLETED" ] || [ "$STATUS" = "FAILED" ]; then break; fi
  sleep 1
done

echo "run status: $STATUS"
if [ "$STATUS" != "COMPLETED" ]; then
  echo "FAIL: run did not complete" >&2
  tail -20 "$LOG" >&2
  exit 1
fi

SCORE=$(curl -sf "http://127.0.0.1:$PORT/api/v1/runs/$RUN_ID" \
  | "$PY" -c "import json,sys; d=json.load(sys.stdin); print(d['run']['golden_path_score'])")
echo "golden path score: $SCORE"

"$PY" - "$SCORE" <<'EOF'
import sys
score = float(sys.argv[1])
if score < 80:
    sys.exit(f"FAIL: score {score} below 80")
print("OK: score >= 80")
EOF

echo "Verifying security endpoint (cached, offline-safe)"
RESULTS=$(curl -sf "http://127.0.0.1:$PORT/api/v1/security/attacks" \
  | "$PY" -c "import json,sys; print(len(json.load(sys.stdin)['results']))")
echo "attacks returned: $RESULTS"

echo "PASS: AgentTrace offline E2E OK"