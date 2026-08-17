# AgentTrace

A lightweight **AI-agent observer**: a Python agent runtime that executes
tool-calling tasks, a Flask API that exposes every run live, and a Next.js
observer UI that shows the golden-path score, memory, trajectory, and
adversarial security results in real time.

You can watch an autonomous agent go *"research → store → email"*, score its
behavior against a golden path, see every tool call and its inputs/outputs,
and confirm the built-in defenses caught simulated attacks — all from one
page.

## Features

- **Real tools, real services.** DuckDuckGo web search, Supabase/PostgREST
  read+write, and Gmail list/read/send. Bring your own credentials or run
  fully offline — unconfigured tools degrade to a graceful skip.
- **Live trajectory.** Every step (tool, input, output, duration, errors) is
  recorded in SQLite and streamed to the UI as the run executes.
- **Golden-path scoring.** Each task type has an expected tool sequence; runs
  are scored 0–100 with deviation detection (missing / wrong-order / extra /
  retry steps) surfaced in the UI and in exported run records.
- **Data flows between steps.** The agent threads the previous tool's output
  into the next action — search results are actually stored in Supabase,
  stored rows are what gets emailed, and `gmail_send` is **gated** so it never
  fires an empty "see attached" email when nothing was stored.
- **Security by default.** Injection-marker stripping + PII redaction before
  anything is persisted, SSRF protection on web search, a Supabase table
  whitelist, and a simulated adversarial attack suite that proves the
  defenses work (run against a throwaway sandbox, never the live registry).
- **Offline-first.** The whole stack runs end-to-end without any credentials,
  so it demos, tests, and scores identically with or without live APIs.

```
agent/     Python runtime: runner, tool registry, trajectory (SQLite),
           memory (MEMORY.md), evaluator (golden-path rubrics),
           security (adversarial attack suite), services.
api/       Flask API (v1): /tasks, /runs, /memory, /security/attacks.
web/       Next.js observer UI (port 3001).
scripts/   start.sh (stack) and run_e2e.sh (offline smoke test).
docs/      design notes, API spec, security model.
```

## How the agent works

At its core is a simple loop:

```
decide next step → execute tool → log trajectory → update memory → score
```

1. **`LogicProcessor.decide(memory, observations)`** picks the next action for
   the goal. The stub maps task keywords to a typed action sequence
   (`research_and_email`, `inbox_summarize`, `data_lookup_report`, or a bounded
   fallback loop) and builds each action's payload from the previous step's
   output — so `supabase_insert` carries real `data`, `gmail_read_email` uses
   the `message_id` observed from the inbox listing, and `gmail_send` only
   fires when the preceding data step actually stored or returned rows.
2. **`ToolRegistry.execute(action)`** runs the tool with a real timeout; typed
   errors only (`not_configured`, `timeout`, `api_error`, `fetch_failed`, …).
3. **`Trajectory.log_step(...)`** persists tool, input, output, success,
   duration and tokens to SQLite.
4. **`MemoryFile`** tracks GOAL, PROGRESS, COMPLETED_STEPS, NEXT_ACTIONS and
   FAILURES in `MEMORY.md`.
5. **`GoldenPathEvaluator.score_run(...)`** compares the executed steps against
   the task type's rubric and returns a score plus deviations.

Runs can be submitted synchronously or asynchronously; the API returns
`202 {run_id}` immediately and executes the loop on a background thread.

## Quick start

Requirements: Python 3.11+, Node 20+. The Termux layout (this repo's dev
environment) uses `/data/data/com.termux/files/usr/bin/python3`.

```bash
# 1. Optional credentials — copy the template and fill in what you use.
#    Everything works without it; unconfigured tools degrade cleanly.
cp .env.example .env

# 2. Install Python deps + UI deps.
pip install -r api/requirements.txt
(cd web && npm install)

# 3. Run the stack: API on :8000, observer UI on :3001.
./scripts/start.sh
```

Open http://localhost:3001, submit a task (e.g. "lookup records from table",
`data_lookup_report`), and watch the run complete with a golden-path score.

## Environment

Configuration lives in `.env` (loaded automatically by the API when present;
never committed — see `.gitignore`). See `.env.example` for every variable:

- `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `SUPABASE_ALLOWED_TABLES` —
  optional Supabase integration. `SUPABASE_ALLOWED_TABLES` is a comma-separated
  allowlist of tables the agent may touch; if creds are set but it is empty,
  the app logs a warning that the whitelist is disabled.
- `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN` — optional
  Gmail send/read. `GMAIL_TEST_TO` is used only by the live test suite.
- `AGENTTRACE_DB_PATH`, `AGENTTRACE_MEMORY_PATH`, `AGENTTRACE_MAX_STEPS`,
  `AGENTTRACE_TOOL_TIMEOUT_S`, `AGENTTRACE_DEBUG`.
- `AGENTTRACE_API_TOKEN` — when set, every `/api/v1/*` route requires
  `Authorization: Bearer <token>` (health + CORS preflight stay open).
- `AGENTTRACE_SNAPSHOT_DIR` — where memory snapshots are written
  (default `.snapshots/` next to the DB).

Secrets never touch the logs, the trajectory DB, or MEMORY.md: tool outputs
are passed through the sanitizer (`agent/security/sanitizer.py`) before they
are persisted.

## Golden-path scoring

Each task type has an expected tool sequence (see
`agent/evaluator/rubrics/__init__.py`):

| task_type           | golden path                                   |
|---------------------|-----------------------------------------------|
| `research_and_email`| `web_search` → `supabase_insert` → `gmail_send`|
| `inbox_summarize`   | `gmail_list_inbox` → `gmail_read_email` → `supabase_insert` |
| `data_lookup_report`| `supabase_select` → `gmail_send`              |

Score = (matched / expected steps) × 100, +10 order bonus when in the correct
order, capped at 100. Deviations (`missing_step`, `wrong_order`, `extra_step`,
`retry`) are shown in the UI and exported with run records.

## API

- `GET /health`
- `POST /api/v1/tasks` `{"task": "...", "task_type": "..."}` → `{run_id, status}`
- `GET /api/v1/runs/<id>` → `{run, steps, deviations}`
- `GET /api/v1/runs/<id>/export` → JSONL training-data format
- `GET /api/v1/memory` → parsed MEMORY.md sections
- `GET /api/v1/security/attacks` → cached adversarial results (run against a
  throwaway fake tool registry, never the live one; cached 60s)

Full spec: `docs/api-spec.md`.

## Tests

```bash
# Python (agent + api). Without .env, the two live-credential tests skip.
/data/data/com.termux/files/usr/bin/python3 -m pytest agent/tests api/tests

# Frontend
(cd web && npx jest)

# Production build + type check
(cd web && npx next build)

# Offline E2E: boots the API, runs a task to COMPLETED, checks score >= 80.
./scripts/run_e2e.sh
```

CI (`.github/workflows/ci.yml`) runs ruff, pytest with `--cov-fail-under=80`,
jest, `next build`, and the offline E2E on Ubuntu.

## Notes / known limits

- The adversarial suite runs against a deterministic fake registry in the API
  so the observer's 5s polling never triggers real Gmail reads or web calls.
- `ruff` is not installable on the Android/Termux platform (no prebuilt
  wheel); lint runs in CI.
- Live email sends happen once per completed `research_and_email` /
  `data_lookup_report` run, addressed to `GMAIL_TEST_TO`. They carry real
  stored content and are suppressed entirely when nothing was stored.