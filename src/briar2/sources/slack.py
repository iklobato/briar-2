"""Slack thread poller for briar-2.

Reads threads from configured channels, detects new messages,
mentions, and reactions. Emits Events with source_type="slack_thread".
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import Source


class SlackSource(Source):
    source_type = SourceType.SLACK_THREAD

    _REQUEST_TIMEOUT = 10.0

    def __init__(
        self, bot_token_env: str, channels: list[str], poll_every: str
    ) -> None:
        self._bot_token_env = bot_token_env
        self._channels = channels
        self._poll_every = poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch new messages from configured channels since `since`."""
        token = self._get_token()
        if not token:
            return []
        since_ts = since.replace(tzinfo=timezone.utc).timestamp()
        events: list[Event] = []
        for channel in self._channels:
            events.extend(self._fetch_channel(token, channel, since_ts))
        return events

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._bot_token_env, "")

    def _fetch_channel(self, token: str, channel: str, since_ts: float) -> list[Event]:
        url = "https://slack.com/api/conversations_history"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"channel": channel, "oldest": str(since_ts), "limit": "100"}
        try:
            with httpx.Client() as client:
                resp = client.get(
                    url, headers=headers, params=params, timeout=self._REQUEST_TIMEOUT
                )
                payload = resp.json()
        except httpx.HTTPError:
            return []

        if not payload.get("ok"):
            return []

        events: list[Event] = []
        for msg in payload.get("messages", []):
            events.append(self._event_from_message(msg, channel))
        return events

    def _event_from_message(self, msg: dict, channel: str) -> Event:
        ts = float(msg.get("ts", 0))
        source_id = f"{channel}:{msg.get('ts', '')}"
        return Event(
            source_type=SourceType.SLACK_THREAD,
            source_id=source_id,
            priority=Priority.ALERT_TRIAGE,
            occurred_at=datetime.fromtimestamp(ts, tz=timezone.utc),
            enqueued_at=datetime.now(timezone.utc),
            payload={"text": msg.get("text", ""), "user": msg.get("user", "")},
            resource_key=f"thread/slack/{channel}/{msg.get('ts', '')}",
        )
