"""File-based priority queue for briar-2 events.

One JSON file per event under `queue_root/<company>/`.
Filenames encode priority + timestamp for ordering (D50).
Atomic operations via a queue-level file lock (D42).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from briar2.lock import ResourceLock
from briar2.models import Event, Priority, SourceType

_FILE_MODE = 0o644
_DEAD_DIR = "dead"
_QUEUE_LOCK_KEY = ".queue"


class EventQueue:
    """Crash-resilient file-based priority queue (D49, D50).

    Each event is a JSON file named: `<priority>_<epochms>_<event_id>.json`
    Lower priority number = higher priority = dequeued first.
    """

    def __init__(self, directory: Path, lock: ResourceLock) -> None:
        self._dir = directory
        self._lock = lock

    def enqueue(self, event: Event) -> None:
        """Write event to queue as a JSON file."""
        payload = self._serialize(event)
        final_name = self._filename(event)
        tmp_path = self._dir / f"tmp_{final_name}"
        final_path = self._dir / final_name
        tmp_path.write_text(json.dumps(payload, default=str) + "\n")
        tmp_path.rename(final_path)

    def dequeue(self) -> Event | None:
        """Pop the highest-priority event (D50).

        Returns None when the queue is empty.
        """
        if not self._lock.acquire(_QUEUE_LOCK_KEY):
            return None
        try:
            files = sorted(self._dir.glob("[0-9]_*.json"))
            if not files:
                return None
            event = self._read(files[0])
            files[0].unlink()
            return event
        finally:
            self._lock.release(_QUEUE_LOCK_KEY)

    def dead_letter(self, event: Event, reason: str) -> Path:
        """Park a failed event for human review (D53)."""
        dead_dir = self._dir / _DEAD_DIR
        dead_dir.mkdir(parents=True, exist_ok=True)
        path = dead_dir / f"{event.event_id}.json"
        body = self._serialize(event)
        body["failed_reason"] = reason
        path.write_text(json.dumps(body, default=str) + "\n")
        return path

    def __len__(self) -> int:
        return sum(1 for _ in self._dir.glob("[0-9]_*.json"))

    def _filename(self, event: Event) -> str:
        return (
            f"{event.priority.value}_"
            f"{event.occurred_at.timestamp():.0f}_"
            f"{event.event_id}.json"
        )

    def _serialize(self, event: Event) -> dict:
        return {
            "event_id": event.event_id,
            "source_type": event.source_type.value,
            "source_id": event.source_id,
            "priority": event.priority.value,
            "occurred_at": event.occurred_at.isoformat(),
            "enqueued_at": event.enqueued_at.isoformat(),
            "resource_key": event.resource_key,
            "payload": event.payload,
        }

    def _read(self, path: Path) -> Event:
        raw = json.loads(path.read_text())
        return Event(
            event_id=raw["event_id"],
            source_type=SourceType(raw["source_type"]),
            source_id=raw["source_id"],
            priority=Priority(raw["priority"]),
            occurred_at=datetime.fromisoformat(raw["occurred_at"]),
            enqueued_at=datetime.fromisoformat(raw["enqueued_at"]),
            resource_key=raw.get("resource_key", ""),
            payload=raw.get("payload", {}),
        )
