# Code of Conduct / Contribution guide for AgentTrace.

## Setup

Python backend (aarch64/Android compatible — no Docker, no Rust-based wheels):

```bash
pip install -r api/requirements.txt
python -m pytest agent/tests api/tests
```

Web observer UI:

```bash
cd web && yarn && yarn dev          # dev server on :3000
npx jest                           # component tests
yarn build && yarn start -p 3001   # prod build + serve (E2E target)
npx playwright test                # E2E (needs API on :8000 + UI on :3001)
```

## Development workflow

- TDD is enforced: write the failing test first (RED), then implement (GREEN),
  then refactor. Coverage target is 80%+.
- All code paths use typed results — never bare `except`.
- Live tool integrations must hit real APIs. Never add a mock behind the
  ToolRegistry interface.
- Ask before: tool integrations, attack implementations, rubric definitions,
  schema changes, new dependencies.

## Structure

- `agent/` — Python agent runtime (core, services, evaluator, security, tools)
- `api/` — Flask API (CodeSentinel-style `src/` factory + blueprints)
- `web/` — Next.js 15 observer UI
- `docs/` — ADRs, API spec, security notes

## Quality gates (before push)

- [ ] All 3 live tools working against real APIs
- [ ] MEMORY.md resumes correctly after process kill
- [ ] 3 task type rubrics with golden path scoring working
- [ ] All 4 security attacks: detected + remediated
- [ ] PyTest coverage 80%+
- [ ] E2E Playwright: 4 flows passing
- [ ] Zero HIGH/CRITICAL CVEs (npm audit + pip audit)
- [ ] Observer UI shows live trajectory updates