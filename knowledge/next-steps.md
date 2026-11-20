# briar-2: next steps

Snapshot: `feat/briar-2-core` @ `1ed1d55` (2026-11-20). Verified: `ruff check` clean, `pytest` 52/52, `find src/briar2 -name '*.py'` lists 17 modules (factory.py removed, registry.py added), `find tests -name '*.py'` lists 9 test files.

## Done

Core poll→dedup→queue→spawn loop with lock, stale detection, escalation; all tests green (52/52).
Sources and actions use registry pattern (`@SourceRegistry.register`, `@ActionRegistry.register`).
Queue has dead letter queue (D53). LLM module wired to Anthropic SDK.

## Next (ordered)

1. **Wire real source implementations** — Slack/GitLab/GitHub/Jira pollers currently return empty lists `[]`. Need real API clients.
2. **Wire real action writers** — Slack/GitLab/GitHub post/approve/comment need real clients (currently draft-only mocks).
3. **Add `ANTHROPIC_API_KEY` to config models** — llm.py reads `os.environ.get("ANTHROPIC_API_KEY")`, config should validate it's set.
4. **Integration test** — mock sources → orchestrator → mock actions, verify event flow end-to-end.
5. **Shadow run** — 7-day run with Gatik config, all outputs as drafts (D17).

## What's left

- Real source implementations (Slack SDK, python-gitlab, PyGithub, jira)
- Real action implementations (Slack post/react, GitLab approve/comment)
- LLM integration is DONE (Anthropic SDK wired in llm.py)
- 7-day shadow run with Gatik config
- Crash recovery testing — kill -9 during agent, verify poller re-enqueues (D35)

## Monitor

- `SourceRegistry` class size (currently 97 lines, hard limit 200)
- Lock contention under real multi-source load
- Import resolution errors (Pyright F401) when adding new modules
- `knowledge/` must be updated before each session end (Stop hook enforces)
