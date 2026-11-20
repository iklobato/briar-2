"""Tests for the agent runner."""

from __future__ import annotations

from pathlib import Path

from fakes import FakeLLM

from briar2.actions.registry import ActionRegistry
from briar2.agent import AgentRunner
from briar2.config import ActionFlags
from briar2.knowledge import KnowledgeStore
from briar2.lock import ResourceLock
from briar2.models import Decision, Event


def test_the_agent_drafts_and_records(
    tmp_path: Path, event: Event, decision: Decision
) -> None:
    """The agent stores the draft and records the outcome."""
    store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
    lock = ResourceLock.from_root(str(tmp_path / "locks"))
    runner = AgentRunner(FakeLLM(decision), ActionRegistry(ActionFlags()), store)

    outcome = runner.spawn(event, lock, "acme")

    assert outcome.success is True
    assert event.event_id in store.scan("acme")
    assert decision.text in (store.read("acme", f"drafts/{event.event_id}") or "")


def test_the_model_gets_the_event_as_context(tmp_path: Path, event: Event) -> None:
    """The model reads the event summary before it decides."""
    store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
    lock = ResourceLock.from_root(str(tmp_path / "locks"))
    fake = FakeLLM(Decision(action="record", text="noted", reason="nothing to do"))
    runner = AgentRunner(fake, ActionRegistry(ActionFlags()), store)

    runner.spawn(event, lock, "acme")

    assert "slack_thread" in fake.contexts[0]
