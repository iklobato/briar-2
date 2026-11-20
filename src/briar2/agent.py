"""Subagent runner for briar-2 (D26).

One agent per event: reads the event plus the correlated knowledge,
asks the model what to do, runs the action under a lock, then records
the result and stores the draft (D17).
"""

from __future__ import annotations

from briar2.actions.registry import ActionRegistry
from briar2.knowledge import KnowledgeStore
from briar2.llm import DecisionLLM
from briar2.lock import ResourceLock
from briar2.models import ActionResult, Event


class AgentRunner:
    """Run one event through: decide → act → record."""

    def __init__(
        self, llm: DecisionLLM, registry: ActionRegistry, store: KnowledgeStore
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._store = store

    def spawn(self, event: Event, lock: ResourceLock, company: str) -> ActionResult:
        """Decide and act on one event."""
        context = self._store.context(company, event)
        decision = self._llm.decide(event, context, self._registry.names())
        action = self._registry.build(decision.action)
        outcome = action.execute(event, lock, decision)
        if outcome.skipped:
            return outcome
        if outcome.draft is not None:
            self._store.save_draft(company, event, outcome.draft)
        self._store.record(company, event, outcome)
        return outcome
