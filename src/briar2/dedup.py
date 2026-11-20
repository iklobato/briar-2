"""Sliding-window deduplication for briar-2 events (D28).

Key = (source_type, source_id, rounded_timestamp).
Window is configurable (default 5 min).
In-memory set, bounded by window size.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from briar2.models import Event

# ponytail: in-memory set; swap for Redis if multi-process dedup ever matters
_DEFAULT_WINDOW_SECONDS = 300


@dataclass(frozen=True)
class _EventKey:
    """Identity of an event for dedup: source, id and rounded timestamp."""

    source_type: str
    source_id: str
    rounded: float


@dataclass(frozen=True)
class _SeenKeys:
    """Keys already seen, oldest first so the window can be purged."""

    order: deque[_EventKey] = field(default_factory=deque)
    keys: set[_EventKey] = field(default_factory=set)


@dataclass(frozen=True)
class SlidingWindowDedup:
    """Drop duplicate events within a sliding time window."""

    window_seconds: int = _DEFAULT_WINDOW_SECONDS
    seen: _SeenKeys = field(default_factory=_SeenKeys)

    def is_duplicate(self, event: Event) -> bool:
        """Return True if this event was already seen within the window."""
        key = self._key(event)
        self._purge(event.occurred_at)
        return key in self.seen.keys

    def mark(self, event: Event) -> None:
        """Record an event as seen."""
        key = self._key(event)
        self._purge(event.occurred_at)
        self.seen.order.append(key)
        self.seen.keys.add(key)

    def _key(self, event: Event) -> _EventKey:
        stamp = event.occurred_at.replace(tzinfo=timezone.utc).timestamp()
        rounded = (int(stamp) // self.window_seconds) * self.window_seconds
        return _EventKey(
            source_type=event.source_type.value,
            source_id=event.source_id,
            rounded=rounded,
        )

    def _purge(self, now: datetime) -> None:
        cutoff = now.replace(tzinfo=timezone.utc).timestamp() - self.window_seconds
        while self.seen.order:
            oldest = self.seen.order[0]
            if oldest.rounded >= cutoff:
                break
            self.seen.order.popleft()
            self.seen.keys.discard(oldest)
