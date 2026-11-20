"""Source base class for briar-2.

Each source polls an external system and emits Events (D19).
Correlation happens in the orchestrator, not here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from briar2.models import Event, Interval, SourceType


@dataclass(frozen=True)
class PollerConfig:
    """The part every poller config shares: how often to poll."""

    poll_every: str


class Source(ABC):
    """Poll a system and return new Events since the last check."""

    source_type: SourceType

    @property
    @abstractmethod
    def poll_every(self) -> str:
        """The poll interval from the company config, like 30s or 5m."""

    @property
    def poll_every_seconds(self) -> int:
        """Poll interval in seconds, taken from the company config."""
        return Interval.parse(self.poll_every).seconds

    @abstractmethod
    def poll(self, since: datetime) -> list[Event]:
        """Return events newer than `since`."""
