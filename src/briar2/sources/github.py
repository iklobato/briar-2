"""GitHub PR poller for briar-2.

Polls PR comments, reviews, and status. Emits Events
with source_type="github_pr". The API base URL comes from the config,
so github.com and GitHub Enterprise both work.
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import datetime, timezone

from github import Github
from github.GithubException import GithubException

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import PollerConfig, Source


_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GitHubConfig(PollerConfig):
    """How to reach the GitHub API for a set of repositories."""

    token_env: str
    repos: list[str]
    url: str

    def pulls_url(self, repo: str) -> str:
        """Full API URL for pull requests of one repo."""
        return f"{self.url}/repos/{repo}/pulls"


class GitHubSource(Source):
    source_type = SourceType.GITHUB_PR
    _config: GitHubConfig
    _client: Github | None
    _REQUEST_TIMEOUT = 10

    def __init__(self, config: GitHubConfig) -> None:
        self._config = config
        token = self._get_token()
        if token:
            self._client = Github(
                token, base_url=self._config.url, timeout=self._REQUEST_TIMEOUT
            )
        else:
            self._client = None

    @property
    def poll_every(self) -> str:
        """The interval from the company config."""
        return self._config.poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch new PR activity since `since`."""
        if self._client is None:
            return []
        events: list[Event] = []
        for repo in self._config.repos:
            events.extend(self._fetch_repo_prs(repo, since))
        return events

    def _fetch_repo_prs(self, repo: str, since: datetime) -> list[Event]:
        try:
            gh_repo = self._client.get_repo(repo)
            pulls = gh_repo.get_pulls(state="all", sort="updated", direction="desc")
        except GithubException:
            _logger.error("github_auth_failed")
            return []
        return [
            self._event_from_pr(pr, repo) for pr in pulls if pr.updated_at > since
        ]

    def _event_from_pr(self, pr, repo: str) -> Event:
        return Event(
            source_type=SourceType.GITHUB_PR,
            source_id=f"{repo}#{pr.number}",
            priority=Priority.ALERT_TRIAGE,
            occurred_at=pr.updated_at.replace(tzinfo=timezone.utc),
            enqueued_at=datetime.now(timezone.utc),
            payload={
                "title": pr.title or "",
                "state": pr.state or "",
                "user": pr.user.login if pr.user else "",
                "url": pr.html_url or "",
            },
            resource_key=f"pr/github/{repo}/{pr.number}",
        )

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._config.token_env, "")
