"""GitHub PR actions for briar-2.

All actions produce drafts — nothing is ever sent (D17).
"""

from __future__ import annotations

from __future__ import annotations

from typing import Any

from briar2.errors import ActionError
from briar2.models import Decision, Draft, Event


class GitHubApproveAction:
    """Approve a PR with a head_sha check (D46)."""

    action_name = "github_approve"

    def __init__(self, *, client: Any = None) -> None:
        self._client = client

    def _do(self, event: Event, decision: Decision) -> Draft:
        """Draft an approval, checking head_sha to avoid stale reviews."""
        repo = event.payload.get("repo", "?")
        pr = event.payload.get("number", "?")
        head = event.payload.get("head_sha", "")
        if not head:
            raise ActionError("no head_sha in event, cannot verify approval target")
        return Draft(
            kind="approve",
            target=f"github:{repo}:{pr}",
            text=(
                f"Approve PR #{pr} in {repo} "
                f"(head_sha={head[:12]})\n\n"
                f"{decision.text}"
            ),
        )


class GitHubCommentAction:
    """Post a review comment on a PR."""

    action_name = "github_comment"

    def __init__(self, *, client: Any = None) -> None:
        self._client = client

    def _do(self, event: Event, decision: Decision) -> Draft:
        repo = event.payload.get("repo", "?")
        pr = event.payload.get("number", "?")
        return Draft(
            kind="comment",
            target=f"github:{repo}:{pr}",
            text=(
                f"Comment on PR #{pr} in {repo}:\n\n"
                f"{decision.text}"
            ),
        )


class GitHubLabelAction:
    """Apply or remove a label on a PR."""

    action_name = "github_label"

    def __init__(self, *, client: Any = None) -> None:
        self._client = client

    def _do(self, event: Event, decision: Decision) -> Draft:
        repo = event.payload.get("repo", "?")
        pr = event.payload.get("number", "?")
        return Draft(
            kind="label",
            target=f"github:{repo}:{pr}",
            text=(
                f"Label PR #{pr} in {repo}:\n\n"
                f"{decision.text}"
            ),
        )
