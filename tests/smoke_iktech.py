"""Smoke test: briar-2 pipeline end-to-end for iktech.

Runs one orchestrator tick with fakes and asserts every stage:
  poll → dedup → queue → agent spawn → lock acquire → action execute → knowledge write

Usage:
    python3 tests/smoke_iktech.py               # verbose
    python3 tests/smoke_iktech.py --crash        # simulate crash mid-agent
    python3 tests/smoke_iktech.py --lock-content # simulate lock contention
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from briar2.config import CompanyConfigLoader
from briar2.dedup import SlidingWindowDedup
from briar2.knowledge import KnowledgeStore
from briar2.lock import ResourceLock
from briar2.models import Decision, Event, Priority, SourceType
from briar2.queue import EventQueue

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fakes import FakeSource  # noqa: E402

# ── constants ────────────────────────────────────────────────────────
_DEDUP_WINDOW_SECONDS = 300
_TEST_EVENT_BASE_ID = 1000
_TMP_ROOT_TEMPLATE = "/tmp/briar2-smoke-{}"
_LOCK_FAIL_RESOURCE = "slack_draft"
_LOCK_TIMEOUT = 5.0
_CRASH_PROCESSED_LIMIT = 1
_POLL_SINCE_SECONDS = 10
_POLL_EVENT_COUNT = 3


@dataclass(frozen=True)
class _QueueContext:
    """Parameters for a single queue processing pass."""

    queue: EventQueue
    fake_llm: "_FakeLLM"
    registry: "_FakeActionRegistry"
    knowledge: KnowledgeStore
    mode: str


class _FakeLock(ResourceLock):
    """Fake lock that can simulate contention."""

    def __init__(self, fail_on: str | None = None) -> None:
        self._fail_on = fail_on
        self.acquired: list[str] = []
        self.released: list[str] = []

    def acquire(self, resource: str, timeout: float = _LOCK_TIMEOUT) -> bool:
        if self._fail_on and self._fail_on in resource:
            return False
        self.acquired.append(resource)
        return True

    def release(self, resource: str) -> None:
        self.released.append(resource)


class _FakeActionRegistry:
    """Fake action registry that records calls instead of doing real IO."""

    def __init__(self) -> None:
        self.executed: list[dict] = []

    def get_action(self, name: str) -> "_FakeAction":
        return _FakeAction(self, name)


class _FakeAction:
    """Fake action that records execution through its registry."""

    def __init__(self, registry: _FakeActionRegistry, action_name: str) -> None:
        self._registry = registry
        self.name = action_name

    def execute(self, event: Event, context: str, lock: ResourceLock) -> "_ActionResult":
        resource = f"test/{self.name}/{event.source_id}"
        if not lock.acquire(resource):
            return _ActionResult(skipped=True, reason="lock busy")
        try:
            self._registry.executed.append(
                {
                    "action": self.name,
                    "event_id": event.source_id,
                    "context_len": len(context),
                }
            )
            return _ActionResult(skipped=False, outcome="ok")
        finally:
            lock.release(resource)


class _FakeLLM:
    """Fake LLM that returns a canned decision."""

    def __init__(self, runner: "_SmokeRunner") -> None:
        self._runner = runner

    def decide(self, event: Event, context: str, actions: list[str]) -> Decision:
        return self._runner._decide(event, actions)


@dataclass(frozen=True)
class _ActionResult:
    """Result of an action execution."""

    skipped: bool
    reason: str = ""
    outcome: str = ""


class _SmokeRunner:
    """Runs the briar-2 pipeline smoke test for iktech."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._company: str = ""
        self._tmp_root: Path | None = None

    def execute_smoke(self, mode: str) -> dict:
        return self._build_report(mode)

    def _build_report(self, mode: str) -> dict:
        report: dict = {"mode": mode, "stages": {}, "ok": True}
        cfg = self._load_config(report)
        if not report["ok"]:
            return report
        self._setup_dirs(cfg)
        try:
            self._run_poll_dedup_queue(cfg, report)
            if report["ok"]:
                self._run_agent_action_knowledge(cfg, report, mode)
        finally:
            self._cleanup()
        return report

    def _load_config(self, report: dict) -> "CompanyConfig | None":
        try:
            cfg = CompanyConfigLoader.load(self._config_path)
            report["stages"]["config"] = {"ok": True, "company": cfg.company, "cap": cfg.cap}
            return cfg
        except (FileNotFoundError, ValueError) as exc:
            report["stages"]["config"] = {"ok": False, "error": str(exc)}
            report["ok"] = False
            return None

    def _setup_dirs(self, cfg: CompanyConfig) -> None:
        self._company = cfg.company
        self._tmp_root = Path(_TMP_ROOT_TEMPLATE.format(int(time.time())))
        cfg.paths.lock_root = str(self._tmp_root / "locks")
        cfg.paths.queue_root = str(self._tmp_root / "queue")
        cfg.paths.knowledge_root = str(self._tmp_root / "knowledge")
        for path in [cfg.paths.lock_root, cfg.paths.queue_root, cfg.paths.knowledge_root]:
            Path(path).mkdir(parents=True, exist_ok=True)

    def _run_poll_dedup_queue(self, cfg: CompanyConfig, report: dict) -> None:
        try:
            dedup, queue = self._setup_queue_stage(cfg)
            deduped = self._poll_and_dedup(dedup, queue)
            report["stages"]["poll_dedup_queue"] = {
                "ok": True,
                "polled": _POLL_EVENT_COUNT,
                "deduped": deduped,
                "in_queue": len(queue),
            }
        except (OSError, ConnectionError) as exc:
            report["stages"]["poll_dedup_queue"] = {"ok": False, "error": str(exc)}
            report["ok"] = False

    def _setup_queue_stage(
        self, cfg: CompanyConfig
    ) -> tuple[SlidingWindowDedup, EventQueue]:
        dedup = SlidingWindowDedup(window_seconds=_DEDUP_WINDOW_SECONDS)
        queue_lock = ResourceLock(Path(cfg.paths.lock_root))
        queue = EventQueue(Path(cfg.paths.queue_root), queue_lock)
        return dedup, queue

    def _poll_and_dedup(
        self, dedup: SlidingWindowDedup, queue: EventQueue
    ) -> int:
        src = FakeSource(
            [self._make_event(idx) for idx in range(_POLL_EVENT_COUNT)]
        )
        last_check = datetime.now(timezone.utc) - timedelta(seconds=_POLL_SINCE_SECONDS)
        events = src.poll(last_check)
        deduped = 0
        for ev in events:
            if not dedup.is_duplicate(ev):
                dedup.mark(ev)
                queue.enqueue(ev)
                deduped += 1
        return deduped

    def _run_agent_action_knowledge(
        self, cfg: CompanyConfig, report: dict, mode: str
    ) -> None:
        try:
            dedup, queue = self._setup_queue_stage(cfg)
            self._enqueue_for_processing(dedup, queue)
            registry = _FakeActionRegistry()
            knowledge = KnowledgeStore(Path(cfg.paths.knowledge_root))
            fake_llm = _FakeLLM(self)
            ctx = _QueueContext(queue, fake_llm, registry, knowledge, mode)
            processed = self._process_queue(ctx)
            report["stages"]["agent_action_knowledge"] = {
                "ok": True,
                "processed": processed,
                "executed": registry.executed,
            }
        except (OSError, ConnectionError) as exc:
            report["stages"]["agent_action_knowledge"] = {"ok": False, "error": str(exc)}
            report["ok"] = False

    def _enqueue_for_processing(
        self, dedup: SlidingWindowDedup, queue: EventQueue
    ) -> None:
        src = FakeSource(
            [self._make_event(idx) for idx in range(_POLL_EVENT_COUNT)]
        )
        last_check = datetime.now(timezone.utc) - timedelta(seconds=_POLL_SINCE_SECONDS)
        for ev in src.poll(last_check):
            if not dedup.is_duplicate(ev):
                dedup.mark(ev)
                queue.enqueue(ev)

    def _process_one_event(
        self, ctx: _QueueContext, ev: Event, processed: int
    ) -> tuple["_ActionResult", int]:
        action = ctx.registry.get_action(
            ctx.fake_llm.decide(ev, "fake context from knowledge", ["slack_draft"]).action
        )
        exec_result = action.execute(ev, "fake context", _FakeLock())
        ctx.knowledge.write(
            self._company, f"event/{ev.source_id}",
            json.dumps({
                "event_id": ev.source_id,
                "action": ctx.fake_llm.decide(ev, "", [""]).action,
                "skipped": exec_result.skipped,
                "ts": self._timestamp(),
            }),
        )
        return exec_result, processed + 1

    def _process_queue(self, ctx: _QueueContext) -> int:
        processed = 0
        while len(ctx.queue) > 0:
            ev = ctx.queue.dequeue()
            if ev is None:
                break
            _, processed = self._process_one_event(ctx, ev, processed)
            if ctx.mode == "crash" and processed >= _CRASH_PROCESSED_LIMIT:
                break
        return processed

    def _decide(self, event: Event, actions: list[str]) -> Decision:
        return Decision(
            action=actions[0],
            text="draft reply to test event",
            reason="smoke test agent decision",
        )

    def _make_event(self, idx: int) -> Event:
        return Event(
            source_type=SourceType.SLACK_THREAD,
            source_id=f"C0CKNHQ52E6/{_TEST_EVENT_BASE_ID + idx}",
            priority=Priority.MR_REVIEW,
            occurred_at=datetime.now(timezone.utc),
            payload={"channel": "C0CKNHQ52E6", "text": f"iktech test event {idx}"},
        )

    def _cleanup(self) -> None:
        if self._tmp_root:
            shutil.rmtree(self._tmp_root, ignore_errors=True)

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


class _Cli:
    """Entry point for the iktech smoke test."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path

    @classmethod
    def with_logger(cls, config_path: Path) -> "_Cli":
        instance = cls(config_path)
        instance._logger = logging.getLogger("smoke_iktech")
        return instance

    def execute(self) -> int:
        parser = argparse.ArgumentParser(description="iktech smoke test")
        parser.add_argument("--crash", action="store_true", help="simulate crash mid-agent")
        parser.add_argument(
            "--lock-content", action="store_true", help="simulate lock contention"
        )
        args = parser.parse_args()
        mode = "crash" if args.crash else "lock-content" if args.lock_content else "normal"
        report = _SmokeRunner(self._config_path).execute_smoke(mode)
        self._log_report(report)
        return 0 if report["ok"] else 1

    def _log_report(self, report: dict) -> None:
        for stage_name, stage_data in report["stages"].items():
            status = "PASS" if stage_data["ok"] else "FAIL"
            self._logger.info("%s %s", status, stage_name)
            self._log_stage(stage_data)
        self._logger.info("")
        label = "iktech smoke test: PASSED" if report["ok"] else "iktech smoke test: FAILED"
        (self._logger.info if report["ok"] else self._logger.error)("%s", label)

    def _log_stage(self, stage_data: dict) -> None:
        if not stage_data["ok"]:
            self._logger.error("  ERROR: %s", stage_data["error"])
        for key, value in stage_data.items():
            if key in ("ok", "error"):
                continue
            self._logger.info("    %s: %s", key, value)


class _App:
    """Bootstrap logger and run the CLI."""

    def __init__(self) -> None:
        pass

    @classmethod
    def with_logger(cls) -> "_App":
        instance = cls()
        instance._logger = logging.getLogger("smoke_iktech")
        return instance

    def execute_smoke(self) -> int:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        config_path = (
            Path(__file__).resolve().parent.parent / "companies/iktech/config.yaml"
        )
        return _Cli.with_logger(config_path).execute()


if __name__ == "__main__":
    sys.exit(_App.with_logger().execute_smoke())
