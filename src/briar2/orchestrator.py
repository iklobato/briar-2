"""Main orchestrator for briar-2 serve loop (D31).

Flow: poll → dedup → queue → decide → action → record.
One process per company (D5).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from briar2.actions.registry import ActionRegistry
from briar2.agent import AgentRunner
from briar2.config import CompanyConfig, CompanyConfigLoader
from briar2.dedup import SlidingWindowDedup
from briar2.errors import ActionError
from briar2.knowledge import KnowledgeStore
from briar2.llm import AnthropicLLM
from briar2.lock import ResourceLock
from briar2.logging import DaemonLogger
from briar2.models import ActionResult, Event
from briar2.queue import EventQueue
from briar2.sources.base import Source
from briar2.sources.factory import SourceFactory
from briar2.stale import StaleDetector, StaleEscalator

_TICK_SECONDS = 5
_DEDUP_WINDOW = 300  # seconds (D28)
_INITIAL_LOOKBACK = timedelta(minutes=30)


@dataclass(frozen=True)
class CompanyState:
    """Everything one company's serve loop needs."""

    company: str
    queue: EventQueue
    dedup: SlidingWindowDedup
    lock: ResourceLock
    sources: list[Source]
    runner: AgentRunner
    cap: int
    store: KnowledgeStore
    stale: StaleDetector
    escalator: StaleEscalator
    last_poll: dict[Source, datetime] = field(default_factory=dict)
    last_seen: dict[Source, datetime] = field(default_factory=dict)
    running: set[asyncio.Task[None]] = field(default_factory=set)


class Orchestrator:
    """Poll sources, dedup, queue, and spawn agents."""

    def __init__(self, config_dir: str, log: logging.Logger | None = None) -> None:
        self._config_dir = config_dir
        self._log = log

    def run_company(self, company: str) -> None:
        """Run the serve loop for one company."""
        config = CompanyConfigLoader.load(
            Path(self._config_dir) / company / "config.yaml"
        )
        asyncio.run(self._serve(config))

    def run_all(self) -> None:
        """Run every configured company in this process.

        Production runs one process per company (D5). This is the local
        convenience mode.
        """
        configs = self._load_configs()
        if not configs:
            return
        asyncio.run(self._serve_all(configs))

    async def _serve_all(self, configs: list[CompanyConfig]) -> None:
        await asyncio.gather(*(self._serve(config) for config in configs))

    def _logger(self) -> logging.Logger:
        """Return the logger, building the daemon logger on first use."""
        if self._log is None:
            self._log = DaemonLogger("orchestrator").build()
        return self._log

    def _load_configs(self) -> list[CompanyConfig]:
        config_dir = Path(self._config_dir)
        if not config_dir.exists():
            return []
        configs = []
        for config_path in sorted(config_dir.iterdir()):
            if config_path.is_dir() and (config_path / "config.yaml").exists():
                configs.append(CompanyConfigLoader.load(config_path / "config.yaml"))
        return configs

    async def _serve(self, config: CompanyConfig) -> None:
        state = self.build_state(config)
        self._logger().info(
            "company=%s starting cap=%d sources=%d",
            config.company,
            state.cap,
            len(state.sources),
        )
        await self._loop(state)

    def build_state(self, config: CompanyConfig) -> CompanyState:
        queue_dir = Path(config.paths.queue_root).expanduser() / config.company
        queue_dir.mkdir(parents=True, exist_ok=True)
        store = KnowledgeStore.from_root(config.paths.knowledge_root)
        return CompanyState(
            company=config.company,
            queue=EventQueue(queue_dir, ResourceLock(queue_dir)),
            dedup=SlidingWindowDedup(window_seconds=_DEDUP_WINDOW),
            lock=ResourceLock.from_root(config.paths.lock_root),
            sources=SourceFactory().build(config.sources),
            runner=self._runner(config, store),
            cap=config.cap,
            store=store,
            stale=self._stale(config, store),
            escalator=StaleEscalator(store, config.company),
        )

    def _runner(self, config: CompanyConfig, store: KnowledgeStore) -> AgentRunner:
        """The agent runner that turns one event into one action."""
        return AgentRunner(
            AnthropicLLM(config.company, config.llm),
            ActionRegistry(config.actions),
            store,
        )

    def _stale(self, config: CompanyConfig, store: KnowledgeStore) -> StaleDetector:
        """The detector that finds failures nobody picked up."""
        threshold = timedelta(minutes=config.stale_after_minutes)
        return StaleDetector(store, config.company, threshold)

    async def _loop(self, state: CompanyState) -> None:
        while True:
            await self.tick(state)
            await asyncio.sleep(_TICK_SECONDS)

    async def tick(self, state: CompanyState) -> None:
        """One pass of the loop: poll the due sources, then spawn agents."""
        self._poll_due_sources(state)
        await self._drain_queue(state)
        self._escalate_stale(state)

    def _poll_due_sources(self, state: CompanyState) -> None:
        now = datetime.now(timezone.utc)
        for source in state.sources:
            if self._is_due(source, state, now):
                self._poll_source(source, state, now)

    def _is_due(self, source: Source, state: CompanyState, now: datetime) -> bool:
        last = state.last_poll.get(source)
        if last is None:
            return True
        return (now - last).total_seconds() >= source.poll_every_seconds

    def _poll_source(self, source: Source, state: CompanyState, now: datetime) -> None:
        since = state.last_seen.get(source, now - _INITIAL_LOOKBACK)
        events = source.poll(since)
        state.last_poll[source] = now
        state.last_seen[source] = now
        for event in events:
            self._try_enqueue(event, state)

    def _try_enqueue(self, event: Event, state: CompanyState) -> None:
        """Enqueue if not a duplicate (D28)."""
        if state.dedup.is_duplicate(event):
            return
        state.dedup.mark(event)
        state.queue.enqueue(event)
        self._logger().info(
            "event_id=%s enqueued source=%s id=%s priority=%s",
            event.event_id,
            event.source_type.value,
            event.source_id,
            event.priority.value,
        )

    async def _drain_queue(self, state: CompanyState) -> None:
        """Spawn one agent per queued event, up to the company cap (D25)."""
        while len(state.running) < state.cap:
            event = state.queue.dequeue()
            if event is None:
                return
            task = asyncio.create_task(self._run_event(event, state))
            state.running.add(task)
            task.add_done_callback(state.running.discard)

    async def _run_event(self, event: Event, state: CompanyState) -> None:
        """Run one event through the agent, off the event loop."""
        self._logger().info("event_id=%s start", event.event_id)
        try:
            outcome = await asyncio.to_thread(
                state.runner.spawn, event, state.lock, state.company
            )
        except ActionError as exc:
            self._logger().error("event_id=%s failed error=%s", event.event_id, exc)
            self._dead_letter(event, str(exc), state)
            return
        self._route_outcome(event, outcome, state)

    def _route_outcome(
        self, event: Event, outcome: ActionResult, state: CompanyState
    ) -> None:
        """Log what the agent did, then retry skips and dead-letter failures."""
        self._logger().info(
            "event_id=%s action=%s success=%s skipped=%s",
            event.event_id,
            outcome.action,
            outcome.success,
            outcome.skipped,
        )
        if outcome.skipped:
            state.queue.enqueue(event)
            return
        if not outcome.success:
            self._dead_letter(event, outcome.detail, state)

    def _dead_letter(self, event: Event, reason: str, state: CompanyState) -> None:
        path = state.queue.dead_letter(event, reason)
        self._logger().error(
            "event_id=%s dead_letter path=%s reason=%s", event.event_id, path, reason
        )

    def _escalate_stale(self, state: CompanyState) -> None:
        """Leave a note for every failure that waited too long (D21)."""
        if not state.stale.due():
            return
        for item in state.escalator.escalate(state.stale.check()):
            self._logger().warning(
                "event_id=%s escalated source=%s processed_at=%s",
                item.event_id,
                item.source_id,
                item.processed_at,
            )
