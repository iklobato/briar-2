"""Anthropic decision client for briar-2 agents (D8).

One model call per event: the model reads the event plus the correlated
knowledge and returns a structured decision (which action, with which
text). The decision is a draft, never a sent message (D17).
"""

from __future__ import annotations

import os
from typing import Any, Literal, Protocol, cast

from anthropic import Anthropic, APIStatusError
from pydantic import BaseModel, create_model

from briar2.config import LLMConfig
from briar2.errors import ActionError, AuthError
from briar2.models import Decision, Event

_MAX_TOKENS = 16000
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2")
_FALLBACK_REJECTED_STATUS = 400

_SYSTEM_PROMPT = """You are the triage agent of briar2, an event driven assistant for one company.

You never send anything. You only propose the draft that a human reviews and sends.

Rules:
- Read the event and the knowledge context before deciding. The context beats your priors.
- Pick the smallest action that moves the event forward.
- If the event needs no reply, pick the action named record.
- If the evidence is thin, pick record and say what is missing in the reason.
- Write the text in plain English, ready to paste. No em dash, no en dash, no apostrophes.
- Always include the full URL of any external item you mention.
- The marker must be one of the check mark, the cross mark or the eyes when the action reacts."""


class DecisionLLM(Protocol):
    """What the agent needs from a model provider."""

    def decide(
        self, event: Event, context: str, action_names: list[str]
    ) -> Decision: ...


class _DecisionFields(Protocol):
    """The fields the model must return for one decision."""

    action: str
    text: str
    reason: str
    marker: str


class ParsedDecision(Protocol):
    """A model response that carries the structured decision."""

    @property
    def parsed_output(self) -> BaseModel | None: ...


class AnthropicLLM:
    """Ask Claude what to do about one event (D8)."""

    def __init__(self, company: str, settings: LLMConfig) -> None:
        self._company = company
        self._settings = settings
        self._api_client: Anthropic | None = None

    def decide(self, event: Event, context: str, action_names: list[str]) -> Decision:
        """Return the agent decision for one event."""
        if not action_names:
            raise ActionError("no actions enabled for this company")
        schema = self._schema(action_names)
        try:
            response = self._request(schema, self._prompt(event, context, action_names))
        except APIStatusError as exc:
            raise ActionError(f"anthropic api error: {exc}") from exc
        parsed = response.parsed_output
        if parsed is None:
            raise ActionError("model returned no structured decision")
        fields = cast(_DecisionFields, parsed)
        return Decision(
            action=fields.action,
            text=fields.text,
            reason=fields.reason,
            marker=fields.marker,
        )

    @property
    def _api(self) -> Anthropic:
        if self._api_client is None:
            self._api_client = self._build_client()
        return self._api_client

    def _build_client(self) -> Anthropic:
        """Build an Anthropic client.

        Priority: ANTHROPIC_BASE_URL (Claude Code proxy) > ANTHROPIC_API_KEY.
        When running inside Claude Code the proxy handles auth, so no key is needed.
        """
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        if base_url:
            return Anthropic(base_url=base_url)
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise AuthError("ANTHROPIC_API_KEY is not set")
        return Anthropic(api_key=key)

    def _schema(self, action_names: list[str]) -> type[BaseModel]:
        """Build the decision schema for the actions this company enables."""
        action_type = Literal[tuple(action_names)]  # type: ignore[valid-type]
        return create_model(
            "AgentDecision",
            action=(action_type, ...),
            text=(str, ...),
            reason=(str, ...),
            marker=(str, ""),
        )

    def _request(self, schema: type[BaseModel], prompt: str) -> ParsedDecision:
        """Ask the API for one structured decision."""
        payload = self._payload(schema, prompt)
        if self._settings.model not in _FALLBACK_MODELS:
            return self._api.messages.parse(**payload)
        return self._parse_with_fallback(payload)

    def _parse_with_fallback(self, payload: dict[str, Any]) -> ParsedDecision:
        """Parse with server-side fallback, retrying plain when the beta is rejected."""
        try:
            return self._api.beta.messages.parse(
                **payload,
                betas=[_FALLBACK_BETA],
                extra_body={"fallbacks": "default"},
            )
        except APIStatusError as exc:
            if exc.status_code != _FALLBACK_REJECTED_STATUS:
                raise
            return self._api.messages.parse(**payload)

    def _payload(self, schema: type[BaseModel], prompt: str) -> dict[str, Any]:
        """Build the request body for one decision."""
        return {
            "model": self._settings.model,
            "max_tokens": _MAX_TOKENS,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self._settings.effort},
            "output_format": schema,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _prompt(self, event: Event, context: str, action_names: list[str]) -> str:
        return "\n".join(
            [
                f"Company: {self._company}",
                f"Source: {event.source_type.value}",
                f"Source id: {event.source_id}",
                f"Occurred at: {event.occurred_at.isoformat()}",
                f"Allowed actions: {', '.join(action_names)}",
                "",
                "Event and knowledge context:",
                context,
            ]
        )
