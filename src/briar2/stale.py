"""Stale detection for briar-2 (D54).

Runs in the same process, read-only on the knowledge store (no lock
needed to read). A result older than the threshold is escalated for
human review (D21, escalation level 2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from briar2.knowledge import KnowledgeStore


class StaleDetector:
    """Find results that were processed long ago and still need a human (D21, D54)."""

    def __init__(
        self, store: KnowledgeStore, company: str, threshold: timedelta
    ) -> None:
        self._store = store
        self._company = company
        self._threshold = threshold

    def check(self) -> list[str]:
        """Return event IDs processed before the cutoff, oldest first."""
        cutoff = datetime.now(timezone.utc) - self._threshold
        stale = [
            event_id
            for event_id, meta in self._store.scan(self._company).items()
            if self._is_stale(meta, cutoff)
        ]
        return sorted(stale)

    def _is_stale(self, meta: dict, cutoff: datetime) -> bool:
        processed_at = meta.get("processed_at")
        if not processed_at:
            return False
        try:
            ts = datetime.fromisoformat(processed_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False
        return ts < cutoff
