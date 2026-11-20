"""Tests for the file-based knowledge store."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from briar2.knowledge import KnowledgeStore
from briar2.models import ActionResult, Event


def test_a_written_note_reads_back(tmp_path: Path) -> None:
    """A written note comes back unchanged."""
    store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))

    store.write("acme", "notes/GAIT-1", "the note body")

    assert store.read("acme", "notes/GAIT-1") == "the note body"


def test_a_missing_note_reads_as_none(tmp_path: Path) -> None:
    """Reading a note that was never written gives nothing."""
    store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))

    assert store.read("acme", "notes/GAIT-1") is None


def test_the_recorded_result_carries_the_outcome(tmp_path: Path, event: Event) -> None:
    """The recorded result keeps the action and the outcome."""
    store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
    outcome = ActionResult(event_id=event.event_id, success=True, action="slack_draft")

    store.record("acme", event, outcome)

    recorded = store.scan("acme")
    assert recorded[event.event_id]["action"] == "slack_draft"
    assert recorded[event.event_id]["success"] == "true"


def test_the_context_holds_earlier_results_of_the_same_resource(
    tmp_path: Path, event: Event
) -> None:
    """An earlier result on the same resource reaches the context."""
    store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
    earlier = ActionResult(
        event_id="older", success=True, action="record", detail="seen before"
    )
    store.record("acme", replace(event, event_id="older"), earlier)

    context = store.context("acme", event)

    assert "Earlier result older" in context


def test_the_context_holds_the_note_of_a_mentioned_ticket(
    tmp_path: Path, event: Event
) -> None:
    """A note about a ticket key in the payload reaches the context."""
    store = KnowledgeStore.from_root(str(tmp_path / "knowledge"))
    store.write("acme", "notes/GAIT-1", "the note body")
    ticket_event = replace(event, payload={"text": "see GAIT-1 please"})

    context = store.context("acme", ticket_event)

    assert "Note GAIT-1" in context
    assert "the note body" in context
