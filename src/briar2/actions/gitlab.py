"""GitLab action executors for briar-2.

Approve carries the head sha so a human can verify the commit before
sending (D46). Comment and label are drafts as well (D17).
"""

from __future__ import annotations

from briar2.actions.base import Action
from briar2.models import Decision, Draft, Event


class GitLabApproveAction(Action):
    """Approve a GitLab MR, with the head sha for verification (D46)."""

    action_name = "gitlab_approve"

    def _do(self, event: Event, decision: Decision) -> Draft:
        head_sha = event.payload.get("head_sha", "")
        text = decision.text
        if head_sha:
            text = f"{text}\nhead_sha: {head_sha}"
        return Draft(kind="approve", target=event.resource_key, text=text)


class GitLabCommentAction(Action):
    """Comment on a GitLab MR."""

    action_name = "gitlab_comment"

    def _do(self, event: Event, decision: Decision) -> Draft:
        return Draft(kind="message", target=event.resource_key, text=decision.text)


class GitLabLabelAction(Action):
    """Add a label to a GitLab MR. The label is the decision text."""

    action_name = "gitlab_label"

    def _do(self, event: Event, decision: Decision) -> Draft:
        return Draft(kind="label", target=event.resource_key, text=decision.text)
