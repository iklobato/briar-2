"""Jira JQL poller for briar-2.

Runs JQL queries, detects new/updated issues. Emits Events
with source_type="jira_issue".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import PollerConfig, Source


@dataclass(frozen=True)
class JiraConfig(PollerConfig):
    """How to reach one Jira instance and one JQL query."""

    token_env: str
    jql: str
    url: str


class JiraSource(Source):
    source_type = SourceType.JIRA_ISSUE
    _config: JiraConfig

    _REQUEST_TIMEOUT = 10.0

    def __init__(self, config: JiraConfig) -> None:
        self._config = config

    @property
    def poll_every(self) -> str:
        """The interval from the company config."""
        return self._config.poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch updated issues matching JQL since `since`."""
        token = self._get_token()
        if not token:
            return []
        since_iso = since.isoformat()
        jql = f"{self._config.jql} AND updated >= '{since_iso}'"
        issues = self._search(token, jql)
        return [self._event_from_issue(issue) for issue in issues]

    def _search(self, token: str, jql: str) -> list[dict]:
        base = self._config.url.rstrip("/")
        url = f"{base}/rest/api/3/search"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        params = {"jql": jql, "maxResults": "50", "fields": "summary,status,updated"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    url, headers=headers, params=params, timeout=self._REQUEST_TIMEOUT
                )
                body = resp.json()
                return body.get("issues", [])
        except httpx.HTTPError:
            return []

    def _event_from_issue(self, issue: dict) -> Event:
        key = issue["key"]
        fields = issue.get("fields", {})
        return Event(
            source_type=SourceType.JIRA_ISSUE,
            source_id=key,
            priority=Priority.ALERT_TRIAGE,
            occurred_at=self._occurred_at(fields),
            enqueued_at=datetime.now(timezone.utc),
            payload={
                "summary": fields.get("summary", ""),
                "status": fields.get("status", {}).get("name", ""),
                "url": f"{self._config.url.rstrip('/')}/browse/{key}",
            },
            resource_key=f"issue/jira/{key}",
        )

    def _occurred_at(self, fields: dict) -> datetime:
        """Parse the issue update time, falling back to now."""
        updated_str = fields.get("updated", "")
        if not updated_str:
            return datetime.now(timezone.utc)
        return datetime.fromisoformat(updated_str.replace("Z", "+00:00"))

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._config.token_env, "")
