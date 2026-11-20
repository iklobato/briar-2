"""Slack thread poller for briar-2.

Reads threads from configured channels, detects new messages
and thread replies. Emits Events with source_type="slack_thread".
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from datetime import datetime, timezone

from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError

from briar2.models import Event, Priority, SourceType
from briar2.sources.base import PollerConfig, Source


_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SlackConfig(PollerConfig):
    """Which Slack channels to read and which token to use."""

    bot_token_env: str
    channels: list[str]


class SlackSource(Source):
    source_type = SourceType.SLACK_THREAD
    _config: SlackConfig
    _client: WebClient | None
    _REQUEST_TIMEOUT = 10.0

    def __init__(self, config: SlackConfig) -> None:
        self._config = config
        token = self._get_token()
        self._client = WebClient(token=token) if token else None

    @property
    def poll_every(self) -> str:
        """The interval from the company config."""
        return self._config.poll_every

    def poll(self, since: datetime) -> list[Event]:
        """Fetch new messages and thread replies from configured channels."""
        if self._client is None:
            return []
        since_ts = since.replace(tzinfo=timezone.utc).timestamp()
        events: list[Event] = []
        for channel in self._config.channels:
            events.extend(self._fetch_channel(channel, since_ts))
        return events

    def _fetch_channel(self, channel: str, since_ts: float) -> list[Event]:
        try:
            resp = self._client.conversations_history(
                channel=channel,
                oldest=str(since_ts),
                limit=100,
                timeout=self._REQUEST_TIMEOUT,
            )
            messages = resp.get("messages", [])
        except SlackApiError as exc:
            error = exc.response.get("error")
            if error in ("invalid_auth", "account_inactive"):
                _logger.error("slack_auth_failed", error=error)
                return []
            raise

        events: list[Event] = []
        for msg in messages:
            events.append(self._event_from_message(msg, channel))
            if msg.get("reply_count"):
                events.extend(self._fetch_thread_replies(channel, msg["ts"]))
        return events

    def _fetch_thread_replies(self, channel: str, ts: str) -> list[Event]:
        try:
            resp = self._client.conversations_replies(
                channel=channel, ts=ts, timeout=self._REQUEST_TIMEOUT
            )
            messages = resp.get("messages", [])
        except SlackApiError:
            return []
        return [self._event_from_message(m, channel) for m in messages[1:]]

    def _event_from_message(self, msg: dict, channel: str) -> Event:
        ts = float(msg.get("ts", 0))
        return Event(
            source_type=SourceType.SLACK_THREAD,
            source_id=f"{channel}:{msg.get('ts', '')}",
            priority=Priority.ALERT_TRIAGE,
            occurred_at=datetime.fromtimestamp(ts, tz=timezone.utc),
            enqueued_at=datetime.now(timezone.utc),
            payload={"text": msg.get("text", ""), "user": msg.get("user", "")},
            resource_key=f"thread/slack/{channel}/{msg.get('ts', '')}",
        )

    def _get_token(self) -> str:
        import os

        return os.environ.get(self._config.bot_token_env, "")
