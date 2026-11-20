"""Fakes for the briar-2 test suite.

Fakes, not mocks: they carry real behaviour so a test asserts on what
the code produced, not on which calls it made.
"""

from __future__ import annotations

from datetime import datetime

from briar2.models import Decision, Event, SourceType
from briar2.sources.base import Source

_FAKE_POLL_EVERY = "1s"


class FakeSource(Source):
    """A source that always returns the same events."""

    source_type = SourceType.SLACK_THREAD

    def __init__(self, events: list[Event]) -> None:
        self._events = events
        self.poll_count = 0

    @property
    def poll_every(self) -> str:
        """The fake polls every second."""
        return _FAKE_POLL_EVERY

    def poll(self, since: datetime) -> list[Event]:
        """Return the canned events, ignoring the cursor."""
        self.poll_count += 1
        return list(self._events)


class FakeLLM:
    """A model that returns one canned decision and keeps the context."""

    def __init__(self, decision: Decision) -> None:
        self._decision = decision
        self.contexts: list[str] = []

    def decide(self, event: Event, context: str, action_names: list[str]) -> Decision:
        """Return the canned decision, remembering the context it got."""
        self.contexts.append(context)
        return self._decision
