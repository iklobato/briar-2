"""Tests for the sliding-window deduplication."""

from __future__ import annotations

from collections.abc import Callable

from briar2.dedup import SlidingWindowDedup
from briar2.models import Event

_WINDOW_SECONDS = 300
_EVENT_STAMP = "2026-11-20T12:00:00+00:00"
_LATER_STAMP = "2026-11-20T12:10:00+00:00"


def test_the_same_event_is_a_duplicate(make_event: Callable[..., Event]) -> None:
    """A marked event reads back as a duplicate."""
    dedup = SlidingWindowDedup(window_seconds=_WINDOW_SECONDS)
    event = make_event()

    dedup.mark(event)

    assert dedup.is_duplicate(event) is True


def test_another_source_id_is_not_a_duplicate(make_event: Callable[..., Event]) -> None:
    """A different source id is never a duplicate."""
    dedup = SlidingWindowDedup(window_seconds=_WINDOW_SECONDS)
    dedup.mark(make_event(source_id="C123:1"))

    assert dedup.is_duplicate(make_event(source_id="C123:2")) is False


def test_an_event_after_the_window_is_not_a_duplicate(
    make_event: Callable[..., Event],
) -> None:
    """The same source id after the window is a new event."""
    dedup = SlidingWindowDedup(window_seconds=_WINDOW_SECONDS)
    dedup.mark(make_event(occurred_at=_EVENT_STAMP))

    later = make_event(occurred_at=_LATER_STAMP)

    assert dedup.is_duplicate(later) is False
