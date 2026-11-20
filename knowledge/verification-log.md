# briar-2: verification log

Snapshot: `feat/briar-2-core` @ `1ed1d55` (2026-11-20). Uncommitted changes in working tree: sources/registry.py, queue.py, orchestrator.py, stale.py, llm.py.

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check src/briar2/` | All checks passed |
| Tests | `python -m pytest tests/ -x -q` | 52 passed in 6.86s |
| Branch | `git branch --show-current` | feat/briar-2-core |
| Commit | `git rev-parse HEAD` | 1ed1d55b1c96e1cb50f0f066d0897eaecd5d6aac |
| Module count | `find src/briar2 -name '*.py'` | 17 files (was 18, factory.py removed) |
| Test count | `find tests -name '*.py'` | 9 files |
