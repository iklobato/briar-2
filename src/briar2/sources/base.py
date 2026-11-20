"""Source base class for briar-2.

Each source polls an external system and emits Events (D19).
Correlation happens in the orchestrator, not here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from briar2.models import Event, Interval, SourceType


class Source(ABC):
    """Poll a system and return new Events since the last check."""

    source_type: SourceType
    _poll_every: str = "60s"

    @property
    def poll_every_seconds(self) -> int:
        """Poll interval in seconds, taken from the company config."""
        return Interval.parse(self._poll_every).seconds

    @abstractmethod
    def poll(self, since: datetime) -> list[Event]:
        """Return events newer than `since`."""
