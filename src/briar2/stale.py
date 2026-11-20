"""Stale detection for briar-2 (D54).

Runs in the same process, read-only on the knowledge store (no lock
needed to read). A result that failed and is still waiting after the
threshold is escalated for human review (D21, escalation level 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from briar2.knowledge import KnowledgeStore

_CHECK_INTERVAL = timedelta(minutes=15)
_ESCALATIONS_TOPIC = "escalations"


@dataclass(frozen=True)
class StaleItem:
    """One failed result that still waits for a human."""

    event_id: str
    source_id: str
    resource_key: str
    processed_at: str
    detail: str


class StaleDetector:
    """Find the failures that waited too long (D21, D54)."""

    def __init__(
        self, store: KnowledgeStore, company: str, threshold: timedelta
    ) -> None:
        self._store = store
        self._company = company
        self._threshold = threshold
        self._last_run: datetime | None = None

    def due(self) -> bool:
        """True when the next check is due."""
        if self._last_run is None:
            return True
        return datetime.now(timezone.utc) - self._last_run >= _CHECK_INTERVAL

    def check(self) -> list[StaleItem]:
        """Return the failures that are old enough."""
        self._last_run = datetime.now(timezone.utc)
        cutoff = self._last_run - self._threshold
        items: list[StaleItem] = []
        for event_id, meta in self._store.scan(self._company).items():
            item = self._to_item(event_id, meta, cutoff)
            if item is not None:
                items.append(item)
        return items

    def _to_item(self, event_id: str, meta: dict, cutoff: datetime) -> StaleItem | None:
        """Build the item for one result, or None when it does not qualify."""
        if meta.get("success") != "false":
            return None
        processed_at = meta.get("processed_at", "")
        if not self._is_older(processed_at, cutoff):
            return None
        return StaleItem(
            event_id=event_id,
            source_id=meta.get("source_id", ""),
            resource_key=meta.get("resource_key", ""),
            processed_at=processed_at,
            detail=meta.get("detail", ""),
        )

    def _is_older(self, processed_at: str, cutoff: datetime) -> bool:
        """True when the result was processed before the cutoff."""
        if not processed_at:
            return False
        try:
            stamp = datetime.fromisoformat(processed_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return False
        return stamp < cutoff


class StaleEscalator:
    """Write one escalation note per stale failure (D21).

    The note lives in the knowledge store, never in a sent message (D17).
    """

    def __init__(self, store: KnowledgeStore, company: str) -> None:
        self._store = store
        self._company = company

    def escalate(self, items: list[StaleItem]) -> list[StaleItem]:
        """Write a note for every item not escalated yet, return those items."""
        fresh: list[StaleItem] = []
        for item in items:
            if self._already_escalated(item.event_id):
                continue
            topic = f"{_ESCALATIONS_TOPIC}/{item.event_id}"
            self._store.write(self._company, topic, self._body(item))
            fresh.append(item)
        return fresh

    def _already_escalated(self, event_id: str) -> bool:
        """True when this failure already has a note."""
        topic = f"{_ESCALATIONS_TOPIC}/{event_id}"
        return self._store.read(self._company, topic) is not None

    def _body(self, item: StaleItem) -> str:
        """Build the text of one escalation note."""
        return (
            f"# Escalation\n\n"
            f"event_id: {item.event_id}\n"
            f"source_id: {item.source_id}\n"
            f"resource_key: {item.resource_key}\n"
            f"processed_at: {item.processed_at}\n"
            f"detail: {item.detail}\n\n"
            "This event failed and is still waiting for a human.\n"
        )
