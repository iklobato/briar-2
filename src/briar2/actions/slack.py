"""Slack action executors for briar-2.

Draft only (D17): never post directly, always produce a draft.
"""

from __future__ import annotations

from briar2.actions.base import Action
from briar2.models import Decision, Draft, Event

_DEFAULT_MARKER = "👀"


class SlackDraftAction(Action):
    """Draft a Slack message for a thread (D17)."""

    action_name = "slack_draft"

    def _do(self, event: Event, decision: Decision) -> Draft:
        return Draft(
            kind="message",
            target=event.resource_key or event.source_id,
            text=decision.text,
        )


class SlackReactAction(Action):
    """Mark the event as handled with an emoji reaction (D18)."""

    action_name = "slack_react"

    def _do(self, event: Event, decision: Decision) -> Draft:
        marker = decision.marker or _DEFAULT_MARKER
        return Draft(
            kind="marker",
            target=event.resource_key or event.source_id,
            text=marker,
        )
