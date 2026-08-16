# AgentTrace API Spec

Base URL: `/api/v1`

## Health

`GET /health` → `{status: "ok", version}`

## Tasks

### Submit a task

`POST /api/v1/tasks`

```json
{"task": "research Python best practices", "task_type": "research_and_email"}
```

`task_type` ∈ `research_and_email | inbox_summarize | data_lookup_report`.

**202** → `{run_id, status: "accepted"}`
**422** → `{error: {code: "VALIDATION_ERROR", message, details}}`

### List runs

`GET /api/v1/tasks` → `{runs: [...]}`

## Runs

`GET /api/v1/runs/{run_id}` → `{run, steps}`

Step schema:

```json
{
  "step_number": 1,
  "tool_called": "web_search",
  "tool_input": {"query": "..."},
  "tool_output": {},
  "success": true,
  "duration_ms": 342,
  "tokens_used": null,
  "timestamp": "ISO8601"
}
```

`GET /api/v1/runs/{run_id}/export` → JSONL (one record per run) for AI
training data. Record shape:

```json
{
  "task": "lookup records from table",
  "task_type": "data_lookup_report",
  "steps": [{"step_number": 1, "tool_called": "supabase_select", "...": "..."}],
  "golden_path_score": 100.0,
  "deviations": [{"kind": "missing_step", "tool": "gmail_send", "detail": "...", "severity": "critical"}],
  "outcome": "COMPLETED"
}
```

Deviation kinds: `missing_step`, `wrong_order`, `extra_step`, `retry`
(severity: info/warning/critical).

**404** → `{error: {code: "NOT_FOUND", ...}}`

## Memory

`GET /api/v1/memory` → `{sections: {GOAL, STATUS, PROGRESS, COMPLETED_STEPS, NEXT_ACTIONS, FAILURES, SESSION_ID}}`

## Security

`GET /api/v1/security/attacks` → `{results: [{attack_type, severity, detected, remediated, evidence}]}`
(implemented in Module 5)

## Errors

All errors use the envelope:

```json
{"error": {"code": "NOT_FOUND", "message": "run not found: x"}}
```

Codes: `NOT_FOUND`, `VALIDATION_ERROR`, `INTERNAL_ERROR`.