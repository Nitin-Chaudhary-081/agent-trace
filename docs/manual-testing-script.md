# AgentTrace — Manual Test & Video Recording Script

This is your walkthrough for testing **everything** in AgentTrace while
recording a demo video. Follow the scenes top to bottom — each one maps to a
feature the reviewer will look for.

## Setup before recording

1. Start the stack (if not already running):

   ```bash
   cd agenttrace
   ./scripts/start.sh
   ```

   - API → http://localhost:8000
   - UI  → http://localhost:3001

2. Health check in a terminal:

   ```bash
   curl http://localhost:8000/health
   # {"status":"ok","version":"0.1.0"}
   ```

3. Recording tips:
   - Record at 1080p+, full window, browser zoom 100%.
   - Clear the Supabase `public_data` table first (optional but nice):
     run a `data_lookup_report` later so the stored rows are visibly fresh.
   - If you demo live Gmail/Supabase, your real creds in `.env` are used —
     emails go to `GMAIL_TEST_TO`. Say this on camera so viewers know.

---

## Scene 0 — Landing page (10s)

Open http://localhost:3001

- Title **"AgentTrace Observer"** visible.
- Four panels: Task Launcher, Memory, Trajectory, and Golden-Path Score +
  Security.

---

## Scene 1 — Launch a task, watch it live (30–60s)

1. In **Task Launcher**: leave task type as `research_and_email`.
2. Type: `research Python web frameworks, store findings in supabase`
3. Click **Run Task**.
4. Watch the live flow:
   - `run_id` appears under the launcher.
   - Trajectory panel lists steps one by one:
     `web_search` → `supabase_insert` → `gmail_send`.
   - Each step shows tool, status, and the input/output snippet.
5. When it settles, **Golden-Path Score** shows **100** and status
   **COMPLETED**.
6. Talk through what happened: searched the web, **actually stored** a note
   in Supabase, and only then sent the email with real content.

---

## Scene 2 — Data was really stored (20s)

Open in a new tab: your Supabase dashboard → `public_data` table.

- Show the new row: the `note` contains your research content (search
  results), NOT boilerplate.
- Optional: open the sent email in Gmail (sent to `GMAIL_TEST_TO`) to show
  the body matches the stored content.

---

## Scene 3 — inbox_summarize (30–45s)

1. Back in the UI, task type → `inbox_summarize`.
2. Task text: `summarize my inbox`
3. Click **Run Task**.
4. Watch the flow: `gmail_list_inbox` → `gmail_read_email` →
   `supabase_insert`.
5. Confirm the final step stored the summary and the score is 100.
6. Note: reads the real inbox (live creds) — that is expected.

---

## Scene 4 — data_lookup_report (30s)

1. Task type → `data_lookup_report`.
2. Task text: `lookup records from table`
3. Click **Run Task**.
4. Watch: `supabase_select` → `gmail_send`.
5. Show the run completes with score 100 and the email was sent with the
   *returned* rows (not a stub).

---

## Scene 5 — Security panel (15s)

- The **Security** panel lists 4 simulated attacks, each showing severity,
  `detected ✅` and `remediated ✅`:
  - `prompt_injection` (critical)
  - `authority_escalation` (high)
  - `privacy_leak` (low)
  - `indirect_injection` (low)
- Explain: these run against a *throwaway sandboxed tool registry*, never
  real Gmail/web/Supabase — so the 5s polling is safe.

---

## Scene 6 — Memory viewer (15s)

- **Memory** panel shows live agent state: `GOAL`, `STATUS`, `SESSION_ID`,
  `PROGRESS`, `COMPLETED_STEPS`, `NEXT_ACTIONS`.
- Reload the page — the run state persists (SQLite + MEMORY.md).

---

## Scene 7 — Edge cases / robustness (30s) — pick 2

1. **Unknown task type** — set task type to `research_and_email` but type a
   random phrase like `random nonsense please do xyz`. The agent should still
   run a bounded fallback loop and settle (no crash).
2. **Repeated runs** — launch the same task twice; each gets a unique
   `run_id`, the score panel tracks the latest.
3. **API directly** (terminal):

   ```bash
   curl -X POST http://localhost:8000/api/v1/tasks \
     -H 'Content-Type: application/json' \
     -d '{"task":"lookup records from table","task_type":"data_lookup_report"}'
   # returns {"run_id":"...","status":"queued"}
   curl http://localhost:8000/api/v1/runs/<run_id>
   ```

---

## Scene 8 — Tests are real (20s, optional)

Show the CI/tests actually run:

```bash
cd agenttrace
/data/data/com.termux/files/usr/bin/python3 -m pytest agent/tests api/tests
(cd web && npx jest)
./scripts/run_e2e.sh
```

- Expect: 115 passed, 2 skipped / 9 jest / E2E PASS.

---

## Close

- Summary line for the video: "AgentTrace — a full agent loop you can watch,
  scored against a golden path, with stored data, real emails, and built-in
  adversarial defenses. Everything you just saw is verified by automated
  tests."

---

## What NOT to do on camera

- Do not show `.env` (contains live Supabase/Gmail secrets).
- Do not show the GitHub token or the tokenized remote URL in
  `.git/config`.
- Do not scroll through `MEMORY.md` if it still has earlier run artifacts
  unless you explain it is agent memory.