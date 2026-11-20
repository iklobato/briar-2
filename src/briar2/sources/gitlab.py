"""GitLab MR poller for briar-2.

Polls MR comments, CI status, and labels. Emits Events
with source_type="gitlab_mr". The instance URL comes from the config,
so gitlab.com and a self-hosted GitLab both work.
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import datetime, timezone

import gitlab
from gitlab.exceptions import GitlabAuthenticationError

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import PollerConfig, Source


_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class GitLabConfig(PollerConfig):
    """How to reach one GitLab instance and one project."""

    token_env: str
    project: str
    url: str

    def merge_requests_url(self) -> str:
        """Full API URL for merge requests of this project."""
        encoded = self.project.replace("/", "%2F")
        return f"{self.url}/api/v4/projects/{encoded}/merge_requests"


class GitLabSource(Source):
    source_type = SourceType.GITLAB_MR
    _config: GitLabConfig
    _client: gitlab.Gitlab | None
    _REQUEST_TIMEOUT = 10.0

    def __init__(self, config: GitLabConfig) -> None:
        self._config = config
        token = self._get_token()
        self._client = (
            gitlab.Gitlab(
                self._config.url, private_token=token, timeout=self._REQUEST_TIMEOUT
            )
            if token
            else None
        )

    @property
    def poll_every(self) -> str:
        """The interval from the company config."""
        return self._config.poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch new MR activity since `since`."""
        if self._client is None:
            return []
        try:
            mrs = self._fetch_mrs(since)
        except GitlabAuthenticationError:
            _logger.error("gitlab_auth_failed")
            return []
        return [self._event_from_mr(mr) for mr in mrs]

    def _fetch_mrs(self, since: datetime) -> list:
        project = self._client.projects.get(self._config.project)
        return project.mergerequests.list(
            updated_after=since.isoformat(), per_page=50
        )

    def _event_from_mr(self, mr) -> Event:
        return Event(
            source_type=SourceType.GITLAB_MR,
            source_id=f"{self._config.project}!{mr.iid}",
            priority=Priority.ALERT_TRIAGE,
            occurred_at=datetime.fromisoformat(mr.updated_at.replace("Z", "+00:00")),
            enqueued_at=datetime.now(timezone.utc),
            payload={
                "title": mr.title or "",
                "state": mr.state or "",
                "author": mr.author["username"] if mr.author else "",
                "url": mr.web_url or "",
            },
            resource_key=f"mr/gitlab/{self._config.project}/{mr.iid}",
        )

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._config.token_env, "")
