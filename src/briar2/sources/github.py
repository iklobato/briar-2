"""GitHub PR poller for briar-2.

Polls PR comments, reviews, and status. Emits Events
with source_type="github_pr".
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import Source


class GitHubSource(Source):
    source_type = SourceType.GITHUB_PR

    _REQUEST_TIMEOUT = 10.0

    def __init__(self, token_env: str, repos: list[str], poll_every: str) -> None:
        self._token_env = token_env
        self._repos = repos
        self._poll_every = poll_every

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
        for repo in self._repos:
            events.extend(self._fetch_repo_prs(headers, repo, since_iso))
        return events

    def _fetch_repo_prs(self, headers: dict, repo: str, since_iso: str) -> list[Event]:
        url = f"https://api.github.com/repos/{repo}/pulls"
        params = {"state": "all", "since": since_iso, "per_page": "50"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    url, headers=headers, params=params, timeout=self._REQUEST_TIMEOUT
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

        return os.environ.get(self._token_env, "")
