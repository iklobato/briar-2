"""File-based knowledge store for briar-2 (D11, D24).

Markdown files under `knowledge_root/<company>/`.
Lock-protected writes (D45). Reads are plain file reads.
"""

from __future__ import annotations

import fcntl
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from briar2.models import ActionResult, Draft, Event

_WRITE_MODE = 0o644  # file permissions for knowledge files
_RESULTS_TOPIC = "results"
_DRAFTS_TOPIC = "drafts"
_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")


class KnowledgeStore:
    """Persist and retrieve company knowledge as markdown."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @classmethod
    def from_root(cls, knowledge_root: str) -> KnowledgeStore:
        """Create store, expanding user home in the path."""
        return cls(Path(knowledge_root).expanduser())

    def read(self, company: str, topic: str) -> str | None:
        """Read a knowledge file. Returns None if missing."""
        path = self._path(company, topic)
        if not path.exists():
            return None
        return path.read_text()

    def write(self, company: str, topic: str, content: str) -> None:
        """Write a knowledge file through a locked descriptor (D45)."""
        path = self._path(company, topic)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_TRUNC, _WRITE_MODE)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.write(fd, content.encode("utf-8"))
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def record(self, company: str, event: Event, outcome: ActionResult) -> None:
        """Record the outcome of one agent run, with a processing stamp."""
        stamp = datetime.now(timezone.utc).isoformat()
        body = (
            f"event_id: {event.event_id}\n"
            f"source_type: {event.source_type.value}\n"
            f"source_id: {event.source_id}\n"
            f"resource_key: {event.resource_key}\n"
            f"action: {outcome.action}\n"
            f"success: {str(outcome.success).lower()}\n"
            f"skipped: {str(outcome.skipped).lower()}\n"
            f"processed_at: {stamp}\n"
            f"detail: {outcome.detail}\n"
        )
        self.write(company, f"{_RESULTS_TOPIC}/{event.event_id}", body)

    def save_draft(self, company: str, event: Event, draft: Draft) -> None:
        """Save a never-sent draft for a human to review (D17)."""
        header = (
            f"# Draft {draft.kind}\n\n"
            f"event_id: {event.event_id}\n"
            f"source_id: {event.source_id}\n"
            f"target: {draft.target}\n"
            f"occurred_at: {event.occurred_at.isoformat()}\n\n"
        )
        self.write(
            company, f"{_DRAFTS_TOPIC}/{event.event_id}", header + draft.text + "\n"
        )

    def scan(self, company: str) -> dict[str, dict]:
        """Return metadata for every recorded result and draft, keyed by event id."""
        out: dict[str, dict] = {}
        results_dir = self._root / company / _RESULTS_TOPIC
        if results_dir.exists():
            for path in sorted(results_dir.glob("*.md")):
                try:
                    out[path.stem] = self._parse_meta(path.read_text())
                except OSError:
                    continue
        drafts_dir = self._root / company / _DRAFTS_TOPIC
        if drafts_dir.exists():
            for path in sorted(drafts_dir.glob("*.md")):
                try:
                    meta = self._parse_meta(path.read_text())
                    meta.setdefault("action", "draft")
                    out[path.stem] = meta
                except OSError:
                    continue
        return out

    def context(self, company: str, event: Event) -> str:
        """Build the correlation blob for one event (D19).

        Joins the event itself, earlier results on the same resource, and
        notes about any ticket key mentioned in the event.
        """
        parts = [self._event_summary(event)]
        parts.extend(self._related_results(company, event))
        parts.extend(self._related_notes(company, event))
        return "\n\n".join(part for part in parts if part)

    def _path(self, company: str, topic: str) -> Path:
        return self._root / company / f"{topic}.md"

    def _parse_meta(self, content: str) -> dict[str, str]:
        meta: dict[str, str] = {}
        for line in content.splitlines():
            key, sep, value = line.partition(": ")
            if sep and key:
                meta[key] = value
        return meta

    def _event_summary(self, event: Event) -> str:
        url = event.payload.get("url", "")
        title = (
            event.payload.get("title")
            or event.payload.get("summary")
            or event.payload.get("text", "")
        )
        head = f"Event: {event.source_type.value} {event.source_id}"
        if url:
            head += f" ({url})"
        return f"{head}\n{title}".strip()

    def _related_results(self, company: str, event: Event) -> list[str]:
        """Earlier results that touch the same resource."""
        related: list[str] = []
        for event_id, meta in self.scan(company).items():
            if event_id == event.event_id:
                continue
            if meta.get("resource_key") != event.resource_key:
                continue
            related.append(
                f"Earlier result {event_id}: action={meta.get('action', '')} "
                f"success={meta.get('success', '')} detail={meta.get('detail', '')}"
            )
        return related

    def _related_notes(self, company: str, event: Event) -> list[str]:
        """Notes stored under any ticket key mentioned in the event."""
        notes: list[str] = []
        for key in self._mentioned_keys(event):
            content = self.read(company, f"notes/{key}")
            if content:
                notes.append(f"Note {key}:\n{content.strip()}")
        return notes

    def _mentioned_keys(self, event: Event) -> list[str]:
        haystack = " ".join(str(value) for value in event.payload.values())
        return list(dict.fromkeys(_KEY_PATTERN.findall(haystack)))
