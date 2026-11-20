"""Tests for the stale detector and the escalation notes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from briar2.knowledge import KnowledgeStore
from briar2.stale import StaleDetector, StaleEscalator

_COMPANY = "acme"
_THRESHOLD = timedelta(minutes=60)
_OLD_STAMP = "2026-11-20T08:00:00+00:00"
_NEW_STAMP = "2026-11-20T23:00:00+00:00"


@pytest.fixture
def store(tmp_path: Path) -> KnowledgeStore:
    """A knowledge store with one company folder."""
    return KnowledgeStore.from_root(str(tmp_path / "knowledge"))


@pytest.fixture
def result_body() -> Callable[[str, str], str]:
    """Build the text of one recorded result."""

    def build(success: str, stamp: str) -> str:
        return (
            "event_id: ev-1\n"
            "source_id: C123:1\n"
            "resource_key: thread/slack/C123:1\n"
            "action: slack_draft\n"
            f"success: {success}\n"
            f"processed_at: {stamp}\n"
            "detail: the remote refused\n"
        )

    return build


def test_a_failed_result_older_than_the_threshold_is_stale(
    store: KnowledgeStore, result_body: Callable[[str, str], str]
) -> None:
    """A failure nobody fixed in time shows up as stale."""
    store.write(_COMPANY, "results/ev-1", result_body("false", _OLD_STAMP))
    detector = StaleDetector(store, _COMPANY, _THRESHOLD)

    items = detector.check()

    assert [item.event_id for item in items] == ["ev-1"]
    assert items[0].detail == "the remote refused"


def test_a_successful_result_is_never_stale(
    store: KnowledgeStore, result_body: Callable[[str, str], str]
) -> None:
    """A result that worked is not waiting for a human."""
    store.write(_COMPANY, "results/ev-1", result_body("true", _OLD_STAMP))
    detector = StaleDetector(store, _COMPANY, _THRESHOLD)

    assert detector.check() == []


def test_a_recent_failure_is_not_stale(
    store: KnowledgeStore, result_body: Callable[[str, str], str]
) -> None:
    """A failure from ten minutes ago is still fresh."""
    store.write(_COMPANY, "results/ev-1", result_body("false", _NEW_STAMP))
    detector = StaleDetector(store, _COMPANY, _THRESHOLD)

    assert detector.check() == []


def test_the_same_failure_is_escalated_only_once(
    store: KnowledgeStore, result_body: Callable[[str, str], str]
) -> None:
    """Escalating twice leaves one note, not two."""
    store.write(_COMPANY, "results/ev-1", result_body("false", _OLD_STAMP))
    detector = StaleDetector(store, _COMPANY, _THRESHOLD)
    escalator = StaleEscalator(store, _COMPANY)

    first = escalator.escalate(detector.check())
    second = escalator.escalate(detector.check())

    assert [item.event_id for item in first] == ["ev-1"]
    assert second == []
    note = store.read(_COMPANY, "escalations/ev-1")
    assert note is not None
    assert "still waiting for a human" in note
