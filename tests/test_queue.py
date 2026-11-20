"""Tests for the file-based priority queue."""

from __future__ import annotations

from collections.abc import Callable

from briar2.models import Event, Priority
from briar2.queue import EventQueue

_EXPECTED_PENDING = 2


def test_dequeues_the_highest_priority_first(
    queue: EventQueue, make_event: Callable[..., Event]
) -> None:
    """A CI fix comes out before a merge request review."""
    queue.enqueue(make_event(priority=Priority.MR_REVIEW))
    queue.enqueue(make_event(priority=Priority.CI_FIX))

    first = queue.dequeue()

    assert first is not None
    assert first.priority == Priority.CI_FIX


def test_dequeue_returns_none_when_the_queue_is_empty(queue: EventQueue) -> None:
    """An empty queue has nothing to pop."""
    assert queue.dequeue() is None


def test_the_event_survives_the_round_trip(
    queue: EventQueue, make_event: Callable[..., Event]
) -> None:
    """The JSON file carries every field back unchanged."""
    original = make_event(source_id="C123:9")

    queue.enqueue(original)
    restored = queue.dequeue()

    assert restored == original


def test_dead_letter_parks_the_event_with_its_reason(
    queue: EventQueue, make_event: Callable[..., Event]
) -> None:
    """A dead letter file keeps the event and why it failed."""
    event = make_event(source_id="C123:dead")

    path = queue.dead_letter(event, "boom")

    assert path.exists()
    assert "boom" in path.read_text()


def test_length_counts_the_waiting_events(
    queue: EventQueue, make_event: Callable[..., Event]
) -> None:
    """The queue length is the number of files waiting."""
    queue.enqueue(make_event(source_id="C123:1"))
    queue.enqueue(make_event(source_id="C123:2"))

    assert len(queue) == _EXPECTED_PENDING
