"""Integration tests: full event flow through the orchestrator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path

from fakes import FakeLLM, FakeSource

from briar2.actions.registry import ActionRegistry
from briar2.agent import AgentRunner
from briar2.config import ActionFlags
from briar2.knowledge import KnowledgeStore
from briar2.lock import ResourceLock
from briar2.models import Decision, Event, Priority, SourceType
from briar2.orchestrator import CompanyState, Orchestrator
from briar2.queue import EventQueue
from briar2.stale import StaleDetector, StaleEscalator

_STAMP = "2026-11-20T12:00:00+00:00"
_DEFAULT_CAP = 2
_STALE_WINDOW = timedelta(minutes=5)


class TestOrchestratorTick:
    """One tick polls sources, deduplicates, queues, and spawns agents."""

    @staticmethod
    def _make_event(event_id: str = "e1") -> Event:
        return Event(
            source_type=SourceType.SLACK_THREAD,
            source_id=f"C123:{event_id}",
            priority=Priority.MR_REVIEW,
            occurred_at=__import__("datetime").datetime.fromisoformat(_STAMP),
            payload={"text": f"hello {event_id}"},
            resource_key=f"thread/slack/C123:{event_id}",
        )

    def _build_state(
        self, tmp_path: Path, events: list[Event], *, cap: int = _DEFAULT_CAP
    ) -> tuple[CompanyState, FakeSource]:
        """Build a CompanyState with fakes for testing."""
        fake_source = FakeSource(events)
        knowledge = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
        store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
        state = CompanyState(
            company="acme",
            queue=EventQueue(tmp_path / "queue", ResourceLock(tmp_path / "queue")),
            dedup=type("D", (), {
                "is_duplicate": lambda s, e: False,
                "mark": lambda s, e: None,
            })(),
            lock=ResourceLock.from_root(str(tmp_path / "locks")),
            sources=[fake_source],
            runner=AgentRunner(
                FakeLLM(Decision(action="slack_draft", text="draft reply", reason="ok")),
                ActionRegistry(ActionFlags()),
                knowledge,
            ),
            cap=cap,
            store=store,
            stale=StaleDetector(knowledge, "acme", _STALE_WINDOW),
            escalator=StaleEscalator(knowledge, "acme"),
        )
        return state, fake_source

    @staticmethod
    def _run_tick(orch: Orchestrator, state: CompanyState) -> None:
        """Run one orchestrator tick synchronously."""
        orch._log = None  # type: ignore[attr-defined]

        async def _tick() -> None:
            await orch.tick(state)

        asyncio.run(_tick())

    def test_events_flow_through_poll_queue_and_agent(
        self, tmp_path: Path
    ) -> None:
        """A polled event reaches the knowledge store as a draft."""
        event = self._make_event()
        state, source = self._build_state(tmp_path, [event])

        state.queue.enqueue(event)
        orch = Orchestrator.__new__(Orchestrator)
        self._run_tick(orch, state)

        # Agent ran: draft stored in knowledge
        records = state.store.scan("acme")
        assert any(v.get("action") == "draft" for v in records.values()), \
            f"expected draft action in {records}"
        # Source was polled
        assert source.poll_count == 1

    def test_duplicate_events_are_dropped(self, tmp_path: Path) -> None:
        """The dedup window filters repeats."""
        event = self._make_event()
        seen: set[str] = set()

        dedup = type("D", (), {
            "is_duplicate": lambda s, e: e.event_id in seen,
            "mark": lambda s, e: seen.add(e.event_id),
        })()

        fake_source = FakeSource([event])
        knowledge = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
        store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
        state = CompanyState(
            company="acme",
            queue=EventQueue(tmp_path / "queue", ResourceLock(tmp_path / "queue")),
            dedup=dedup,
            lock=ResourceLock.from_root(str(tmp_path / "locks")),
            sources=[fake_source],
            runner=AgentRunner(
                FakeLLM(Decision(action="record", text="", reason="dup")),
                ActionRegistry(ActionFlags()),
                knowledge,
            ),
            cap=_DEFAULT_CAP,
            store=store,
            stale=StaleDetector(knowledge, "acme", _STALE_WINDOW),
            escalator=StaleEscalator(knowledge, "acme"),
        )

        # First poll: event is new, gets queued and dequeued
        orch = Orchestrator.__new__(Orchestrator)
        self._run_tick(orch, state)

        # Second poll: event is duplicate, dedup drops it
        self._run_tick(orch, state)

        # Queue should be empty: duplicate was dropped, not re-enqueued
        assert state.queue.dequeue() is None
