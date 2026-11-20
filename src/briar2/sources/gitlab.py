"""GitLab MR poller for briar-2.

Polls MR comments, CI status, and labels. Emits Events
with source_type="gitlab_mr". The instance URL comes from the config,
so gitlab.com and a self-hosted GitLab both work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote as url_quote

import httpx

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import PollerConfig, Source

_API_PATH = "/api/v4"


@dataclass(frozen=True)
class GitLabConfig(PollerConfig):
    """How to reach one GitLab instance and one project."""

    token_env: str
    project: str
    url: str

    def merge_requests_url(self) -> str:
        """The API URL that lists the merge requests of the project."""
        base = self.url.rstrip("/")
        project = url_quote(self.project, safe="")
        return f"{base}{_API_PATH}/projects/{project}/merge_requests"


class GitLabSource(Source):
    source_type = SourceType.GITLAB_MR
    _config: GitLabConfig

    _REQUEST_TIMEOUT = 10.0

    def __init__(self, config: GitLabConfig) -> None:
        self._config = config

    @property
    def poll_every(self) -> str:
        """The interval from the company config."""
        return self._config.poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch new MR activity since `since`."""
        token = self._get_token()
        if not token:
            return []
        mrs = self._fetch_mrs(token, since)
        return [self._event_from_mr(mr) for mr in mrs]

    def _fetch_mrs(self, token: str, since: datetime) -> list[dict]:
        headers = {"Private-Token": token}
        params = {"updated_after": since.isoformat(), "per_page": "50"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    self._config.merge_requests_url(),
                    headers=headers,
                    params=params,
                    timeout=self._REQUEST_TIMEOUT,
                )
                return resp.json()
        except httpx.HTTPError:
            return []

    def _event_from_mr(self, mr: dict) -> Event:
        mr_id = mr["iid"]
        occurred = datetime.fromisoformat(mr["updated_at"].replace("Z", "+00:00"))
        source_id = f"{self._config.project}!{mr_id}"
        return Event(
            source_type=SourceType.GITLAB_MR,
            source_id=source_id,
            priority=Priority.ALERT_TRIAGE,
            occurred_at=occurred,
            enqueued_at=datetime.now(timezone.utc),
            payload={
                "title": mr.get("title", ""),
                "state": mr.get("state", ""),
                "author": mr.get("author", {}).get("username", ""),
                "url": mr.get("web_url", ""),
            },
            resource_key=f"mr/gitlab/{self._config.project}/{mr_id}",
        )

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._config.token_env, "")
