"""Action base class for briar-2.

Every action acquires a ResourceLock before executing (D41).
Actions produce a draft — nothing is ever sent (D17).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from briar2.errors import ActionError
from briar2.lock import ResourceLock
from briar2.models import ActionResult, Decision, Draft, Event

_LOCK_TIMEOUT = 5.0  # D43
_NO_RESOURCE = "no resource_key to lock"
_LOCK_CONTENTION = "lock contention"


class Action(ABC):
    """Execute an action on a resource, wrapped in a lock."""

    action_name: str = ""

    def execute(
        self, event: Event, lock: ResourceLock, decision: Decision
    ) -> ActionResult:
        """Acquire the lock, run the action, release the lock (D41, D42)."""
        resource = event.resource_key or event.source_id
        if not resource:
            return self._failure(event, _NO_RESOURCE)
        if not lock.acquire(resource, timeout=_LOCK_TIMEOUT):
            return self._skipped(event)
        try:
            draft = self._do(event, decision)
        except ActionError as exc:
            return self._failure(event, str(exc))
        finally:
            lock.release(resource)
        return self._success(event, draft)

    def _success(self, event: Event, draft: Draft) -> ActionResult:
        """Build the result of an action that produced its draft."""
        return ActionResult(
            event_id=event.event_id,
            success=True,
            action=self.action_name,
            detail=draft.text,
            draft=draft,
        )

    def _failure(self, event: Event, detail: str) -> ActionResult:
        """Build the result of an action that failed."""
        return ActionResult(
            event_id=event.event_id,
            success=False,
            action=self.action_name,
            detail=detail,
        )

    def _skipped(self, event: Event) -> ActionResult:
        """Build the result of an action that could not take the lock."""
        return ActionResult(
            event_id=event.event_id,
            success=False,
            action=self.action_name,
            skipped=True,
            skip_reason=_LOCK_CONTENTION,
        )

    @abstractmethod
    def _do(self, event: Event, decision: Decision) -> Draft:
        """Build the draft for this event. Never sends anything."""


class RecordAction(Action):
    """Record the event without any external action (D6, status change)."""

    action_name = "record"

    def _do(self, event: Event, decision: Decision) -> Draft:
        return Draft(
            kind="record",
            target=event.resource_key or event.source_id,
            text=decision.reason or decision.text,
        )
