# briar-2: knowledge index

Snapshot: `feat/briar-2-core` @ `1ed1d55` (2026-11-20). Verified: `git rev-parse HEAD` + `ruff check` clean + `pytest` 52/52. Uncommitted changes: sources/registry.py, queue.py, orchestrator.py, stale.py, llm.py, knowledge/ docs.

## Status at a glance
- **Done:** Core poll→dedup→queue→spawn loop with lock, stale detection, escalation; sources and actions use registry pattern; queue has dead letter queue (D53); LLM module wired to Anthropic SDK; all tests green (52/52)
- **Discovered:** `Orchestrator` hard-capped at 200 lines; test files must use classes; `SourceRegistry` replaces `SourceFactory`; `PollingSource` → `Source` naming
- **Next steps:** Wire real API clients (Slack/GitLab/GitHub/Jira), add ANTHROPIC_API_KEY to config, real action writers, integration test
- **What's left:** Real source/action implementations (currently return empty lists/mock), 7-day shadow run with Gatik config, crash recovery testing
- **Monitor:** Class size creep in `Orchestrator`/`SourceRegistry`, import resolution (Pyright F401) when adding modules, `knowledge/` must be updated before each session end

## Topics
- `code-quality.md`: lint/typecheck fixes applied across sessions (ruff, pyright, immutable-rules violations)
- `next-steps.md`: remaining implementation work, ordered by priority

## Session log
- 2026-11-20: Replaced `sources/factory.py` with `sources/registry.py` using `@SourceRegistry.register` decorator pattern (matching `ActionRegistry`). Updated `orchestrator.py` to use `SourceRegistry.build()`. Removed `SourceFactory`. Added dead letter queue to `queue.py`. All 52 tests passing, ruff clean.
