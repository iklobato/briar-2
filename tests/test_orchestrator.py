"""End-to-end tests of the orchestrator: poll, queue, agent, action."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest
from fakes import FakeLLM, FakeSource

from briar2.actions.registry import ActionRegistry
from briar2.agent import AgentRunner
from briar2.config import ActionFlags, CompanyConfig
from briar2.dedup import SlidingWindowDedup
from briar2.knowledge import KnowledgeStore
from briar2.lock import ResourceLock
from briar2.models import Decision, Event
from briar2.orchestrator import CompanyState, Orchestrator
from briar2.queue import EventQueue
from briar2.stale import StaleDetector, StaleEscalator

_COMPANY = "acme"
_CAP = 2
_STALE_AFTER = timedelta(minutes=60)
_OLD_STAMP = "2026-11-20T08:00:00+00:00"


@dataclass(frozen=True)
class Harness:
    """A serve-loop state wired to the fakes, plus what it wrote."""

    state: CompanyState
    store: KnowledgeStore
    llm: FakeLLM
    event: Event


@pytest.fixture
def harness(tmp_path: Path, event: Event, decision: Decision) -> Harness:
    """A serve-loop state wired to fakes instead of the real pollers."""
    store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
    fake = FakeLLM(decision)
    directory = tmp_path / "queue"
    directory.mkdir(parents=True, exist_ok=True)
    state = CompanyState(
        company=_COMPANY,
        queue=EventQueue(directory, ResourceLock(directory)),
        dedup=SlidingWindowDedup(),
        lock=ResourceLock.from_root(str(tmp_path / "locks")),
        sources=[FakeSource([event])],
        runner=AgentRunner(fake, ActionRegistry(ActionFlags()), store),
        cap=_CAP,
        store=store,
        stale=StaleDetector(store, _COMPANY, _STALE_AFTER),
        escalator=StaleEscalator(store, _COMPANY),
    )
    return Harness(state=state, store=store, llm=fake, event=event)


async def test_a_tick_polls_the_source_and_starts_one_agent(
    harness: Harness,
) -> None:
    """One tick polls the source and starts an agent for the event."""
    orchestrator = Orchestrator("companies", log=logging.getLogger("briar2.test"))

    await orchestrator.tick(harness.state)

    assert len(harness.state.running) == 1
    assert len(harness.state.queue) == 0

    await asyncio.gather(*harness.state.running)


async def test_the_agent_writes_the_draft_and_the_result(harness: Harness) -> None:
    """The agent leaves a draft and a recorded result behind."""
    orchestrator = Orchestrator("companies", log=logging.getLogger("briar2.test"))

    await orchestrator.tick(harness.state)
    await asyncio.gather(*harness.state.running)

    recorded = harness.store.scan(_COMPANY)
    assert recorded[harness.event.event_id]["action"] == "slack_draft"
    assert recorded[harness.event.event_id]["success"] == "true"
    draft = harness.store.read(_COMPANY, f"drafts/{harness.event.event_id}")
    assert "Draft reply for the thread" in (draft or "")


async def test_the_same_event_is_only_handled_once(harness: Harness) -> None:
    """A second poll of the same event starts no second agent."""
    orchestrator = Orchestrator("companies", log=logging.getLogger("briar2.test"))

    await orchestrator.tick(harness.state)
    await orchestrator.tick(harness.state)
    await asyncio.gather(*harness.state.running)

    assert len(harness.llm.contexts) == 1


async def test_a_failure_that_waited_too_long_is_escalated(harness: Harness) -> None:
    """A failed result older than the threshold leaves a note for the human."""
    harness.store.write(
        _COMPANY,
        "results/old-event",
        "event_id: old-event\n"
        "source_id: C123:1\n"
        "resource_key: thread/slack/C123:1\n"
        "action: slack_draft\n"
        "success: false\n"
        f"processed_at: {_OLD_STAMP}\n"
        "detail: the remote refused\n",
    )
    orchestrator = Orchestrator("companies", log=logging.getLogger("briar2.test"))

    await orchestrator.tick(harness.state)
    await asyncio.gather(*harness.state.running)

    note = harness.store.read(_COMPANY, "escalations/old-event")
    assert note is not None
    assert "still waiting for a human" in note


def test_build_state_wires_the_config(tmp_path: Path) -> None:
    """The config decides the company, the cap and the queue folder."""
    config = CompanyConfig.model_validate(
        {
            "company": _COMPANY,
            "cap": _CAP,
            "paths": {"queue_root": str(tmp_path / "queue")},
        }
    )
    orchestrator = Orchestrator("companies", log=logging.getLogger("briar2.test"))

    state = orchestrator.build_state(config)

    assert state.company == _COMPANY
    assert state.cap == _CAP
    assert (tmp_path / "queue" / _COMPANY).is_dir()
