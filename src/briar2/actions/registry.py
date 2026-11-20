"""Registry of the actions a company enables (D6).

The model picks one of the names the registry offers, so a company
config decides which actions exist at all.
"""

from __future__ import annotations

from briar2.actions.base import Action, RecordAction
from briar2.actions.gitlab import (
    GitLabApproveAction,
    GitLabCommentAction,
    GitLabLabelAction,
)
from briar2.actions.github import (
    GitHubApproveAction,
    GitHubCommentAction,
    GitHubLabelAction,
)
from briar2.actions.slack import SlackDraftAction, SlackReactAction
from briar2.config import ActionFlags


class ActionRegistry:
    """Build the actions one company is allowed to run."""

    def __init__(self, flags: ActionFlags) -> None:
        self._flags = flags

    def names(self) -> list[str]:
        """Action names the model may choose from."""
        names = ["record"]
        if self._flags.slack_draft:
            names.extend(["slack_draft", "slack_react"])
        if self._flags.gitlab_approve:
            names.append("gitlab_approve")
        names.extend(["gitlab_comment", "gitlab_label"])
        if self._flags.github_pr_review:
            names.extend(["github_approve", "github_comment", "github_label"])
        return names

    def build(self, name: str) -> Action:
        """Build the action for a name. Unknown names fall back to record."""
        if name == "slack_draft":
            return SlackDraftAction()
        if name == "slack_react":
            return SlackReactAction()
        if name == "gitlab_approve":
            return GitLabApproveAction()
        if name == "gitlab_comment":
            return GitLabCommentAction()
        if name == "gitlab_label":
            return GitLabLabelAction()
        if name == "github_approve":
            return GitHubApproveAction()
        if name == "github_comment":
            return GitHubCommentAction()
        if name == "github_label":
            return GitHubLabelAction()
        return RecordAction()
