"""Shared fixtures for the briar-2 test suite."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from briar2.knowledge import KnowledgeStore
from briar2.lock import ResourceLock
from briar2.models import Decision, Event, Priority, SourceType
from briar2.queue import EventQueue

_COMPANY = "acme"
_EVENT_STAMP = "2026-11-20T12:00:00+00:00"
_EVENT_TEXT = "CI is red on the merge request"
_DEFAULT_SOURCE_ID = "C123:1"


@pytest.fixture
def company() -> str:
    """The company name used across the suite."""
    return _COMPANY


@pytest.fixture
def event() -> Event:
    """One Slack thread event."""
    return Event(
        source_type=SourceType.SLACK_THREAD,
        source_id=_DEFAULT_SOURCE_ID,
        priority=Priority.MR_REVIEW,
        occurred_at=datetime.fromisoformat(_EVENT_STAMP),
        payload={"text": _EVENT_TEXT, "url": "https://example.test/thread/1"},
        resource_key=f"thread/slack/{_DEFAULT_SOURCE_ID}",
    )


@pytest.fixture
def decision() -> Decision:
    """The decision a fake model returns."""
    return Decision(
        action="slack_draft",
        text="Draft reply for the thread",
        reason="CI is red",
    )


@pytest.fixture
def make_event() -> Callable[..., Event]:
    """Build an event with the given source id, priority and timestamp."""

    def _build(
        source_id: str = _DEFAULT_SOURCE_ID,
        priority: Priority = Priority.MR_REVIEW,
        occurred_at: str = _EVENT_STAMP,
    ) -> Event:
        return Event(
            source_type=SourceType.SLACK_THREAD,
            source_id=source_id,
            priority=priority,
            occurred_at=datetime.fromisoformat(occurred_at),
            payload={"text": _EVENT_TEXT},
            resource_key=f"thread/slack/{source_id}",
        )

    return _build


@pytest.fixture
def store(tmp_path: Path) -> KnowledgeStore:
    """A knowledge store rooted in the test tmp dir."""
    return KnowledgeStore.from_root(str(tmp_path / "knowledge"))


@pytest.fixture
def lock(tmp_path: Path) -> ResourceLock:
    """A resource lock rooted in the test tmp dir."""
    return ResourceLock.from_root(str(tmp_path / "locks"))


@pytest.fixture
def queue(tmp_path: Path) -> EventQueue:
    """A priority queue rooted in the test tmp dir."""
    directory = tmp_path / "queue"
    directory.mkdir(parents=True, exist_ok=True)
    return EventQueue(directory, ResourceLock(directory))


@pytest.fixture
def config_path(tmp_path: Path) -> Callable[[str], Path]:
    """Write a config body into the tmp dir and return its path."""

    def _write(body: str) -> Path:
        path = tmp_path / "config.yaml"
        path.write_text(body)
        return path

    return _write
