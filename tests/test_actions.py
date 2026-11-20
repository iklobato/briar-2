"""Tests for the action executors."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from briar2.actions.base import Action
from briar2.actions.slack import SlackDraftAction
from briar2.errors import ActionError
from briar2.lock import ResourceLock
from briar2.models import Decision, Draft, Event, Priority, SourceType

_EVENT_STAMP = "2026-11-20T12:00:00+00:00"
_LOCK_CONTENTION = "lock contention"
_NO_RESOURCE = "no resource_key to lock"


class FailingAction(Action):
    """An action whose remote side always refuses."""

    action_name = "failing"

    def _do(self, event: Event, decision: Decision) -> Draft:
        """Always fail with the reason the remote gave."""
        raise ActionError("the remote refused")


def test_the_draft_is_produced_and_the_lock_is_released(
    tmp_path: Path, event: Event, decision: Decision
) -> None:
    """The action drafts the text and frees the lock."""
    lock = ResourceLock.from_root(str(tmp_path / "locks"))

    outcome = SlackDraftAction().execute(event, lock, decision)

    assert outcome.success is True
    assert outcome.draft is not None
    assert outcome.draft.text == decision.text
    assert lock.held() == []


def test_a_busy_lock_skips_the_action(tmp_path: Path, event: Event) -> None:
    """Another holder of the resource makes the action skip."""
    root = str(tmp_path / "locks")
    holder = ResourceLock.from_root(root)
    holder.acquire(event.resource_key)
    lock = ResourceLock.from_root(root)
    decision = Decision(action="slack_draft", text="hello", reason="because")

    outcome = SlackDraftAction().execute(event, lock, decision)

    assert outcome.skipped is True
    assert outcome.skip_reason == _LOCK_CONTENTION


def test_an_event_without_a_resource_fails(tmp_path: Path) -> None:
    """An event with no resource key cannot be locked."""
    event = Event(
        source_type=SourceType.SLACK_THREAD,
        source_id="",
        priority=Priority.MR_REVIEW,
        occurred_at=datetime.fromisoformat(_EVENT_STAMP),
    )
    lock = ResourceLock.from_root(str(tmp_path / "locks"))
    decision = Decision(action="slack_draft", text="hello", reason="because")

    outcome = SlackDraftAction().execute(event, lock, decision)

    assert outcome.success is False
    assert outcome.detail == _NO_RESOURCE


def test_a_failing_action_reports_the_error(tmp_path: Path, event: Event) -> None:
    """An action error becomes a failed result with the message."""
    lock = ResourceLock.from_root(str(tmp_path / "locks"))
    decision = Decision(action="failing", text="hello", reason="because")

    outcome = FailingAction().execute(event, lock, decision)

    assert outcome.success is False
    assert outcome.detail == "the remote refused"
    assert lock.held() == []
