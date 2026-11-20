"""GitLab MR poller for briar-2.

Polls MR comments, CI status, and labels. Emits Events
with source_type="gitlab_mr".
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote as url_quote

import httpx

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import Source


class GitLabSource(Source):
    source_type = SourceType.GITLAB_MR

    _REQUEST_TIMEOUT = 10.0

    def __init__(self, token_env: str, project: str, poll_every: str) -> None:
        self._token_env = token_env
        self._project = project
        self._poll_every = poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch new MR activity since `since`."""
        token = self._get_token()
        if not token:
            return []
        mrs = self._fetch_mrs(token, since)
        return [self._event_from_mr(mr) for mr in mrs]

    def _fetch_mrs(self, token: str, since: datetime) -> list[dict]:
        url = f"https://gitlab.com/api/v4/projects/{url_quote(self._project, safe='')}/merge_requests"
        headers = {"Private-Token": token}
        params = {"updated_after": since.isoformat(), "per_page": "50"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    url, headers=headers, params=params, timeout=self._REQUEST_TIMEOUT
                )
                return resp.json()
        except httpx.HTTPError:
            return []

    def _event_from_mr(self, mr: dict) -> Event:
        mr_id = mr["iid"]
        occurred = datetime.fromisoformat(mr["updated_at"].replace("Z", "+00:00"))
        source_id = f"{self._project}!{mr_id}"
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
            resource_key=f"mr/gitlab/{self._project}/{mr_id}",
        )

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._token_env, "")
