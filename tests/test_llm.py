"""Tests for the Anthropic LLM client (proxy and key auth)."""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import patch

import pytest

from briar2.errors import AuthError
from briar2.llm import AnthropicLLM
from briar2.models import Event, Priority, SourceType


_STAMP = "2026-11-20T12:00:00+00:00"


@pytest.fixture
def event() -> Event:
    return Event(
        source_type=SourceType.SLACK_THREAD,
        source_id="C123:1",
        priority=Priority.MR_REVIEW,
        occurred_at=datetime.fromisoformat(_STAMP),
        payload={"text": "hello"},
        resource_key="thread/slack/C123:1",
    )


class TestAnthropicLLM:
    """The LLM client picks the right auth method."""

    def test_uses_proxy_when_base_url_is_set(self, event: Event) -> None:
        """ANTHROPIC_BASE_URL → proxy client, no key needed."""
        settings = type("S", (), {"model": "claude-opus-5-5", "effort": "low"})()
        with patch.dict(os.environ, {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8899"}):
            llm = AnthropicLLM("acme", settings)
            client = llm._build_client()

        assert str(client._base_url) == "http://127.0.0.1:8899"

    def test_falls_back_to_api_key_when_no_proxy(self, event: Event) -> None:
        """No proxy → uses ANTHROPIC_API_KEY."""
        settings = type("S", (), {"model": "claude-opus-5-5", "effort": "low"})()
        fake_key = "sk-test-123"
        with patch.dict(os.environ, {}, clear=True):
            os.environ["ANTHROPIC_API_KEY"] = fake_key
            llm = AnthropicLLM("acme", settings)
            client = llm._build_client()
            del os.environ["ANTHROPIC_API_KEY"]

        assert client._api_key_auth["X-Api-Key"] == fake_key

    def test_raises_when_neither_proxy_nor_key_is_set(self, event: Event) -> None:
        """No proxy, no key → AuthError."""
        settings = type("S", (), {"model": "claude-opus-5-5", "effort": "low"})()
        llm = AnthropicLLM("acme", settings)
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(AuthError, match="ANTHROPIC_API_KEY"):
                llm._build_client()
