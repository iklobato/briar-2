"""Jira JQL poller for briar-2.

Runs JQL queries, detects new/updated issues. Emits Events
with source_type="jira_issue".
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import datetime, timezone

from jira import JIRA
from jira.exceptions import JIRAError

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import PollerConfig, Source


_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class JiraConfig(PollerConfig):
    """How to reach one Jira instance and one JQL query."""

    token_env: str
    jql: str
    url: str


class JiraSource(Source):
    source_type = SourceType.JIRA_ISSUE
    _config: JiraConfig
    _client: JIRA | None
    _REQUEST_TIMEOUT = 10.0

    def __init__(self, config: JiraConfig) -> None:
        self._config = config
        token = self._get_token()
        if token and self._config.url:
            self._client = JIRA(
                server=self._config.url,
                token_auth=token,
                timeout=self._REQUEST_TIMEOUT,
                get_server_info=False,
            )
        else:
            self._client = None

    @property
    def poll_every(self) -> str:
        """The interval from the company config."""
        return self._config.poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch updated issues matching JQL since `since`."""
        if self._client is None:
            return []
        try:
            issues = self._search(since)
        except JIRAError:
            _logger.error("jira_auth_failed")
            return []
        return [self._event_from_issue(issue) for issue in issues]

    def _search(self, since: datetime) -> list:
        since_iso = since.isoformat()
        jql = f"{self._config.jql} AND updated >= '{since_iso}'"
        return self._client.search_issues(
            jql, maxResults=50, fields="summary,status,updated"
        )

    def _event_from_issue(self, issue) -> Event:
        key = issue.key
        fields = issue.fields
        updated = getattr(fields, "updated", None)
        if not updated:
            updated = datetime.now(timezone.utc)
        return Event(
            source_type=SourceType.JIRA_ISSUE,
            source_id=key,
            priority=Priority.ALERT_TRIAGE,
            occurred_at=updated,
            enqueued_at=datetime.now(timezone.utc),
            payload={
                "summary": fields.summary or "",
                "status": fields.status.name if fields.status else "",
                "url": f"{self._config.url.rstrip('/')}/browse/{key}",
            },
            resource_key=f"issue/jira/{key}",
        )

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._config.token_env, "")
