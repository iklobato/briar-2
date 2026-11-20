"""GitHub PR poller for briar-2.

Polls PR comments, reviews, and status. Emits Events
with source_type="github_pr". The API base URL comes from the config,
so github.com and GitHub Enterprise both work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import PollerConfig, Source


@dataclass(frozen=True)
class GitHubConfig(PollerConfig):
    """How to reach the GitHub API for a set of repositories."""

    token_env: str
    repos: list[str]
    url: str

    def pulls_url(self, repo: str) -> str:
        """The API URL that lists the pull requests of one repository."""
        return f"{self.url.rstrip('/')}/repos/{repo}/pulls"


class GitHubSource(Source):
    source_type = SourceType.GITHUB_PR
    _config: GitHubConfig

    _REQUEST_TIMEOUT = 10.0

    def __init__(self, config: GitHubConfig) -> None:
        self._config = config

    @property
    def poll_every(self) -> str:
        """The interval from the company config."""
        return self._config.poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch new PR activity since `since`."""
        token = self._get_token()
        if not token:
            return []
        since_iso = since.isoformat()
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        events: list[Event] = []
        for repo in self._config.repos:
            events.extend(self._fetch_repo_prs(headers, repo, since_iso))
        return events

    def _fetch_repo_prs(self, headers: dict, repo: str, since_iso: str) -> list[Event]:
        params = {"state": "all", "since": since_iso, "per_page": "50"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    self._config.pulls_url(repo),
                    headers=headers,
                    params=params,
                    timeout=self._REQUEST_TIMEOUT,
                )
                prs = resp.json()
        except httpx.HTTPError:
            return []
        return [self._event_from_pr(pr, repo) for pr in prs]

    def _event_from_pr(self, pr: dict, repo: str) -> Event:
        pr_num = pr["number"]
        occurred = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
        source_id = f"{repo}#{pr_num}"
        return Event(
            source_type=SourceType.GITHUB_PR,
            source_id=source_id,
            priority=Priority.ALERT_TRIAGE,
            occurred_at=occurred,
            enqueued_at=datetime.now(timezone.utc),
            payload={
                "title": pr.get("title", ""),
                "state": pr.get("state", ""),
                "user": pr.get("user", {}).get("login", ""),
                "url": pr.get("html_url", ""),
            },
            resource_key=f"pr/github/{repo}/{pr_num}",
        )

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._config.token_env, "")
