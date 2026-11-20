"""Tests for the core value objects."""

from __future__ import annotations

from datetime import datetime

import pytest

from briar2.errors import ConfigError
from briar2.models import Event, Interval, Priority, SourceType

_SECONDS_IN_30S = 30
_SECONDS_IN_5M = 300
_SECONDS_IN_1H = 3600
_EVENT_STAMP = "2026-11-20T12:00:00+00:00"


def test_interval_parses_seconds() -> None:
    """A 30s interval is 30 seconds."""
    assert Interval.parse("30s").seconds == _SECONDS_IN_30S


def test_interval_parses_minutes() -> None:
    """A 5m interval is 300 seconds."""
    assert Interval.parse("5m").seconds == _SECONDS_IN_5M


def test_interval_parses_hours() -> None:
    """A 1h interval is 3600 seconds."""
    assert Interval.parse("1h").seconds == _SECONDS_IN_1H


def test_interval_rejects_an_unknown_suffix() -> None:
    """A bad suffix is a config error naming the accepted forms."""
    with pytest.raises(ConfigError) as failure:
        Interval.parse("5x")

    assert "use 30s, 5m or 1h" in str(failure.value)


def test_interval_rejects_a_missing_amount() -> None:
    """A suffix without an amount is a config error."""
    with pytest.raises(ConfigError) as failure:
        Interval.parse("m")

    assert "bad interval 'm'" in str(failure.value)


def test_two_events_never_share_an_id() -> None:
    """Every event gets its own id."""
    first = Event(
        source_type=SourceType.SLACK_THREAD,
        source_id="C123:1",
        priority=Priority.MR_REVIEW,
        occurred_at=datetime.fromisoformat(_EVENT_STAMP),
    )
    second = Event(
        source_type=SourceType.SLACK_THREAD,
        source_id="C123:1",
        priority=Priority.MR_REVIEW,
        occurred_at=datetime.fromisoformat(_EVENT_STAMP),
    )

    assert first.event_id != second.event_id
