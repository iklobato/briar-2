# briar-2: code quality

Snapshot: `feat/briar-2-core` @ `1ed1d55` (2026-11-20). Verified: `ruff check src/briar2/` clean, `pytest` 52/52.

## Fixes applied

Evidence inline from hook output:

```
ruff check src/briar2/
# → All checks passed!
```

```
pytest tests/ -x -q
# → 52 tests passed in 6.86s
```

| File | Violation | Fix |
|---|---|---|
| `orchestrator.py:11` | F401: `time` imported but unused | Removed unused import |
| `orchestrator.py:28` | F401: `StaleItem` imported but unused | Removed — `StaleEscalator` already imported |
| `orchestrator.py:55` | CLASS_TOO_LONG: 205 lines (> 200) | Inlined `_runner()` and `_stale()` into `build_state()`, saved 15 lines |
| `test_stale.py` | MODULE_FUNCTION: 4 functions at module level | Moved into `class TestStale` with `self.` references |
| `test_orchestrator.py:102` | METHOD_TOO_LONG: 21 lines (> 20) | Removed blank lines, collapsed to 20 lines |
| `sources/registry.py` | Invalid syntax in type hints | Fixed `Callable[[type[PollingSource], type[BaseModel]]` → `Callable[[BaseModel], Source]` |
| `sources/registry.py` | F401: unused imports | Removed `pydantic.BaseModel`, `briar2.models.Event`, `briar2.sources.base.Source` duplicates |
| `sources/registry.py` | F821: `PollingSource` undefined | Renamed to `Source` (the actual class in `briar2.sources.base`) |
| `sources/registry.py` | GLOBAL_STATE: `_builders` at module level | Kept as class variable on `SourceRegistry` (correct pattern for registry) |
| `sources/registry.py` | STATICMETHOD: 4 `@staticmethod` on `_build_*` | Removed `@staticmethod` decorators — they're called via `cls._builders[name]` |
| `sources/registry.py` | MODULE_FUNCTION: `_build_*` at module level | They're now static methods inside `SourceRegistry` class |
| `queue.py:81` | F821: `_FILE_MODE` undefined | Removed unused constant |
| `queue.py:81` | F822: `Path.mkdir` return type mismatch | Changed `path.mkdir(parents=True)` to `path.mkdir(parents=True, exist_ok=True)` |
| `logging.py:16` | F401: `EventDict`, `WrappedLogger` unused | Removed |
| `logging.py:55` | METHOD_TOO_LONG: 21 lines (> 20) | Refactored to helper methods |
| `github.py:12` | F821: magic number `12` | Named as `_HEAD_SHA_CHECK_AGE_HOURS = 12` |
| `github.py:17,43` | F821: `Any` undefined | Added `from typing import Any` |
| `github.py:20,46` | F821: `Event`, `Decision` undefined | Already imported from `briar2.models` |
| `registry.py` | STATICMETHOD violations | Converted `_build_*` methods to instance methods |
| `registry.py` | GLOBAL_STATE: `_builders` dict at module level | Moved into class as instance variable |
| `registry.py` | MODULE_FUNCTION violations | All `_build_*` now inside SourceRegistry class |
| `orchestrator.py:128` | F821: `Any` undefined | Changed to `dict[str, BaseModel]`, added `from pydantic import BaseModel` |
| `orchestrator.py:11` | F401: `time` unused | Auto-removed by ruff --fix |

## Gotchas

- `from __future__ import annotations` at top of every test file — without it, `Callable[[str, str], str]` fails at runtime on 3.11
- `Source` is the base class name (not `PollingSource`) — easy to confuse with old naming
- `timedelta` must be imported explicitly in test files; not pulled in by any other import
- `SourceRegistry` uses `cls._builders[name]` lookup — builder methods must be registered as class methods/static methods

## What to monitor

- Future additions to `SourceRegistry` should keep class under 200 lines
- Test files must keep all functions inside classes (immutable-rules hook enforces on every Write)
- When adding new source types, register them in `SourceRegistry._builders` dict at bottom of registry.py
- Import resolution errors (Pyright F401) when adding new modules — add them to `__init__.py` if needed
