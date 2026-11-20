"""Core data models for briar-2.

All models are plain dataclasses — no Pydantic dependency here so they
can be serialized to JSON for the file-based queue without extra work.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from briar2.errors import ConfigError


class SourceType(str, Enum):
    SLACK_THREAD = "slack_thread"
    SLACK_MENTION = "slack_mention"
    GITLAB_MR = "gitlab_mr"
    GITHUB_PR = "github_pr"
    JIRA_ISSUE = "jira_issue"


class Priority(int, Enum):
    """Action priority ordering (D34)."""

    CI_FIX = 0  # highest — blocks humans
    MR_REVIEW = 1
    ALERT_TRIAGE = 2
    STATUS_CHANGE = 3  # lowest


@dataclass(frozen=True)
class Interval:
    """A duration in seconds, parsed from a config string like 30s or 5m."""

    seconds: int

    _SUFFIXES = {"s": 1, "m": 60, "h": 3600}

    @classmethod
    def parse(cls, text: str) -> Interval:
        """Parse 30s / 5m / 1h. Raises ConfigError on bad input."""
        value = text.strip().lower()
        suffix = value[-1] if value else ""
        if suffix not in cls._SUFFIXES:
            raise ConfigError(f"bad interval {text!r}: use 30s, 5m or 1h")
        try:
            amount = int(value[:-1])
        except ValueError as exc:
            raise ConfigError(f"bad interval {text!r}: use 30s, 5m or 1h") from exc
        return Interval(seconds=amount * cls._SUFFIXES[suffix])


@dataclass(frozen=True)
class Event:
    """One polled event from a source.

    Attributes:
        source_type: Which source produced this event.
        source_id: Stable ID from the source (e.g. MR number, thread TS).
        priority: Action priority (D34).
        occurred_at: When the event happened (source timestamp, not poll time).
        data: Source-specific payload (message body, URL, author, etc.).
        resource_key: Key for locking (e.g. "mr/gitlab/123").
    """

    source_type: SourceType
    source_id: str
    priority: Priority
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    resource_key: str = ""

    # Assigned at enqueue time, not by the source
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Draft:
    """A produced action that is never sent (D17).

    Attributes:
        kind: What the draft does — message, marker, label, approve, record.
        target: Where it would go (channel, thread, MR key).
        text: The content, ready for a human to send.
    """

    kind: str
    target: str
    text: str


@dataclass(frozen=True)
class Decision:
    """What the agent decided to do about one event (D8)."""

    action: str
    text: str
    reason: str
    marker: str = ""


@dataclass(frozen=True)
class ActionResult:
    """Outcome of an action execution."""

    event_id: str
    success: bool
    action: str  # e.g. "slack_draft", "gitlab_approve"
    detail: str = ""
    skipped: bool = False
    skip_reason: str = ""
    draft: Draft | None = None
