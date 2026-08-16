# ADRs — AgentTrace

## ADR-001: Python agent runtime + Flask API + Next.js observer

**Status:** Accepted (Module 1)

**Context:** AgentTrace must run on aarch64/Android with no Docker and no
Rust-based pip wheels. The project also reuses proven CodeSentinel patterns.

**Decision:**
- Agent runtime in pure-Python (`agent/`), stdlib `sqlite3` for trajectory
  persistence (aarch64-safe).
- Flask API with a `src/` package + application factory + blueprints, matching
  CodeSentinel layout.
- Next.js 15 (TypeScript) for the observer UI.
- MEMORY.md as the durable agent-state file, read/written under file locks.

**Consequences:** Live tool integrations (Supabase, Gmail) must be pure-Python
clients; any system dependency must be installable on aarch64.

## ADR-002: Typed Result pattern everywhere

**Status:** Accepted (Module 1)

**Context:** The spec forbids bare `except` and requires typed errors.

**Decision:** Every tool returns `ToolResult`; every API error uses the
`{error: {code, message}}` envelope via `ApiError`. Registry timeouts and
unknown tools surface as failed `ToolResult`s so the agent loop can continue
and log them.

## ADR-003: Keyword-based logic processor stub

**Status:** Accepted (Module 1), superseded in Module 3

**Context:** The runner needs a deterministic, testable `decide()` before the
LLM-backed reasoning slot lands.

**Decision:** `LogicProcessor.plan_for_task()` maps task keywords to typed
action sequences. The interface is stable so Module 3 can swap the stub for
LLM reasoning without touching the runner.

## ADR-004: Live tools only, no mocks

**Status:** Accepted (Module 3)

**Context:** The JD requires proving integrations against real APIs.

**Decision:** Supabase, Gmail, and Web Search tools must hit real endpoints.
The ToolRegistry interface never receives mock implementations behind the
`invoke()` boundary.

## ADR-005: Golden path scoring in Module 1

**Status:** Accepted (Module 1)

**Context:** The runner needed a completion signal and a score immediately.

**Decision:** `GoldenPathEvaluator` uses a subsequence matcher
(step_score + 10 order bonus, capped at 100). Module 4 replaces this with
per-task-type rubrics and deviation reports.

## ADR-006: Supabase via PostgREST REST client, not supabase-py

**Status:** Accepted (Module 2)

**Context:** The spec bans Rust-based pip wheels on aarch64/Android.

**Decision:** The `supabase-py` client pulls in `pydantic-core` (Rust), so it
cannot install on this target. AgentTrace talks to Supabase's PostgREST REST
API (`/rest/v1/...`) via the pure-Python `requests` client instead. Zero mocks —
real HTTP against real Supabase endpoints.

## ADR-007: Rolling deque memory summarization

**Status:** Accepted (Module 2)

**Context:** MEMORY.md must stay inside the context window as runs grow long.

**Decision:** PROGRESS is a rolling deque. Newest entries append; oldest drop
once the rendered file exceeds 4000 chars. Deterministic and testable — no LLM
dependency. Session state (GOAL, SESSION_ID, COMPLETED_STEPS) is preserved
through truncation.

## ADR-009: Web search via Bing HTML scrape, not DuckDuckGo

**Status:** Accepted (Module 3)

**Context:** The spec allows scraping a search engine with requests + bs4. The
initial DuckDuckGo HTML endpoint returns 202/captcha from this host.

**Decision:** `WebSearchTool` scrapes Bing organic results (`li.b_algo`),
decoding the `u` base64 param from `/ck/a` redirect wrappers (which carry a
stray prefix byte — the decoder tries offsets). It walks up to 5 results
skipping bot-blocked pages (403/429) before returning `fetch_failed`. Timeout
is enforced with a worker thread (real enforcement even for injected
transports).

## ADR-010: Gmail via OAuth2 refresh-token REST, not google-api-python-client

**Status:** Accepted (Module 3)

**Context:** `google-api-python-client` is a heavy dependency with its own
auth plumbing; the platform bans Rust-based wheels, and pure-python REST keeps
the tool surface identical to the Supabase tool.

**Decision:** `GmailTool` exchanges GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET +
GMAIL_REFRESH_TOKEN for an access token via the OAuth2 token endpoint, then
calls the Gmail REST API directly with requests. No extra client library.
Input validation happens before any network call; missing creds degrade to a
typed `not_configured` failure.

## ADR-011: Live-tool credential gating

**Status:** Accepted (Module 3)

**Context:** Zero mocks is required, but the environment does not yet carry
Supabase/Gmail credentials.

**Decision:** All three tools are real integrations with zero mocks. Tools
whose credentials are absent return typed `not_configured` failures that the
runner treats as failed steps — never a crash. Web Search needs no
credentials and is exercised live. Supabase/Gmail live tests are gated on env
vars and skip otherwise; they run the moment creds are provided.

## ADR-012: Per-task-type rubrics with deviation flags

**Status:** Accepted (Module 4)

**Context:** Module 4 needs objective, verifiable rubrics per task type.

**Decision:** Rubrics live in `agent/evaluator/rubrics/` and define the golden
path tool sequence for three task types: research_and_email
[web_search, supabase_insert, gmail_send], inbox_summarize
[gmail_list_inbox, gmail_read_email, supabase_insert], data_lookup_report
[supabase_select, gmail_send]. Scoring uses the spec formula
(matched/expected * 100 + 10 order bonus, capped at 100). Four deviation
types are flagged as typed records: missing_step, wrong_order, extra_step,
retry. Task type falls back to GOAL keywords when not supplied.

## ADR-013: Trajectory mirror to Supabase agent_runs

**Status:** Accepted (Module 4)

**Context:** Every agent step must be observable in Supabase, not just local
SQLite.

**Decision:** `TrajectoryMirror` posts the run record plus one row per step to
the `agent_runs` PostgREST table after a run completes. It shares the
no-mock / creds-absent-noop posture of every other live integration
(ADR-011). Run + steps are also stored in local SQLite (WAL) for offline
development.

## ADR-014: Four-attack adversarial suite

**Status:** Accepted (Module 5)

**Context:** The JD requires proving prompt-injection resistance, auth
boundaries, privacy hygiene, and data-trust handling.

**Decision:** `AdversarialSuite` builds four attacks against the live tool
registry — prompt_injection (tool-output sanitizer), authority_escalation
(supabase table whitelist from Module 3), privacy_leak (PII scrubber on
outputs), indirect_injection (Supabase row values treated as untrusted
strings). Each implements setup/execute/detect/remediate and emits
{attack_type, severity, detected, remediated, evidence}. Severity drops to
`low` when the attack is not detected. Sanitization is centralized in
`agent/security/sanitizer.py` and shared by attacks 1 and 4.

## ADR-015: Observer UI as client-side polling dashboard

**Status:** Accepted (Module 6)

**Context:** The observer UI must show live agent execution without heavy
server-push infrastructure.

**Decision:** All four panels are client components polling the Flask REST
API: trajectory polls every 2s, memory every 5s, security every 5s. A task
launcher posts to /api/v1/tasks and feeds the returned run_id into the
trajectory + score panels. CORS allows localhost:3000/3001. E2E coverage is
Playwright against the real running stack.

## ADR-008: Resume semantics for stopped runs

**Status:** Accepted (Module 2)

**Context:** A process may die mid-run (or hit the step cap). Restart should
continue, not reset.

**Decision:** Any session with a non-empty GOAL whose status is not COMPLETED is
resumable via `start_or_resume()` / `AgentRunner.resume()`. COMPLETED_STEPS
drives the continuation point; SESSION_ID is preserved across the restart.
FAILED and STOPPED_MAX_STEPS both resume.