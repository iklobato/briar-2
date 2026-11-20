"""Company configuration loader.

Each company has a YAML file under companies/<name>/config.yaml.
The config is strict (unknown keys = error) via Pydantic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from briar2.errors import ConfigError
from briar2.models import Interval


class SourceConfig(BaseModel):
    """Base for every source block."""

    model_config = ConfigDict(extra="forbid")

    poll_every: str = Field(
        default="60s", description="Poll interval (e.g. 30s, 5m, 1h)"
    )

    @field_validator("poll_every")
    @classmethod
    def _valid_interval(cls, value: str) -> str:
        Interval.parse(value)
        return value


class SlackSourceConfig(SourceConfig):
    """Slack thread + mention polling."""

    bot_token_env: str = Field(
        default="SLACK_BOT_TOKEN", description="Env var holding xoxb- token"
    )
    channels: list[str] = Field(default_factory=list, description="Channel IDs to poll")


class GitLabSourceConfig(SourceConfig):
    """GitLab MR polling."""

    token_env: str = Field(
        default="GITLAB_TOKEN", description="Env var holding PRIVATE_TOKEN"
    )
    project: str = Field(description="namespace/project slug")
    url: str = Field(
        default="https://gitlab.com", description="GitLab instance URL, self-hosted ok"
    )


class GitHubSourceConfig(SourceConfig):
    """GitHub PR polling."""

    token_env: str = Field(default="GITHUB_TOKEN", description="Env var holding PAT")
    repos: list[str] = Field(default_factory=list, description="owner/repo slugs")
    url: str = Field(
        default="https://api.github.com",
        description="GitHub API base URL, Enterprise is https://host/api/v3",
    )


class JiraSourceConfig(SourceConfig):
    """Jira JQL polling."""

    jql: str = Field(description="JQL query to run")
    url: str = Field(default="", description="Jira instance URL")
    token_env: str = Field(
        default="JIRA_TOKEN", description="Env var holding API token"
    )


class ActionFlags(BaseModel):
    """Which actions are enabled for this company."""

    model_config = ConfigDict(extra="forbid")

    slack_draft: bool = Field(default=True, description="Post drafts to Slack threads")
    gitlab_approve: bool = Field(default=False)
    ci_fix_attempts: int = Field(default=3, ge=0, le=10)


class LLMConfig(BaseModel):
    """Which model decides what to do with an event (D8)."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(default="claude-opus-5-5", description="Anthropic model id")
    effort: str = Field(
        default="medium", description="Reasoning effort: low, medium, high"
    )
    api_key_env: str = Field(
        default="ANTHROPIC_API_KEY", description="Env var holding the API key"
    )


class PathsConfig(BaseModel):
    """Where briar-2 stores its runtime files."""

    model_config = ConfigDict(extra="forbid")

    knowledge_root: str = Field(default="~/.cache/briar/knowledge/")
    lock_root: str = Field(default="~/.cache/briar/locks/")
    queue_root: str = Field(default="~/.cache/briar/queue/")


class CompanyConfig(BaseModel):
    """Full configuration for one company."""

    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1)
    cap: int = Field(
        default_factory=lambda: os.cpu_count() or 4,
        ge=1,
        description="Max parallel agents (D25, D37)",
    )
    sources: dict[str, Any] = Field(default_factory=dict)
    actions: ActionFlags = Field(default_factory=ActionFlags)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    stale_after_minutes: int = Field(
        default=60, ge=1, description="When a result needs a human"
    )


@dataclass(frozen=True)
class _Block:
    """One YAML block to validate: the raw mapping, its label and the file."""

    raw: dict
    label: str
    path: Path


class CompanyConfigLoader:
    """Validate + load company YAML configs.

    Usage::

        config = CompanyConfigLoader.load(Path("companies/gatik/config.yaml"))
    """

    _SOURCE_TYPES: dict[str, type[BaseModel]] = {
        "slack": SlackSourceConfig,
        "gitlab": GitLabSourceConfig,
        "github": GitHubSourceConfig,
        "jira": JiraSourceConfig,
    }

    @classmethod
    def load(cls, path: Path) -> CompanyConfig:
        """Load, validate, and return a CompanyConfig."""
        raw = cls._load_yaml(path)
        raw["sources"] = cls._parse_sources(raw.get("sources", {}), path)
        raw["actions"] = cls._parse_nested(
            _Block(raw.get("actions", {}), "actions", path), ActionFlags
        )
        raw["llm"] = cls._parse_nested(
            _Block(raw.get("llm", {}), "llm", path), LLMConfig
        )
        raw["paths"] = cls._parse_nested(
            _Block(raw.get("paths", {}), "paths", path), PathsConfig
        )

        try:
            return CompanyConfig.model_validate(raw)
        except ValidationError as exc:
            raise ConfigError(
                f"{path}: validation failed\n{cls._format_errors(exc)}"
            ) from exc

    @classmethod
    def _load_yaml(cls, path: Path) -> dict:
        import yaml

        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: top-level must be a mapping")
        return raw

    @classmethod
    def _parse_nested(cls, block: _Block, model: type[BaseModel]) -> BaseModel:
        """Validate one nested block against its model."""
        if not isinstance(block.raw, dict):
            raise ConfigError(f"{block.path}: {block.label} must be a mapping")
        try:
            return model.model_validate(block.raw)
        except ValidationError as exc:
            raise ConfigError(
                f"{block.path}: {block.label} validation failed\n{cls._format_errors(exc)}"
            ) from exc

    @classmethod
    def _parse_sources(cls, raw: dict[str, dict], path: Path) -> dict[str, Any]:
        """Validate every source block against its own model."""
        sources: dict[str, Any] = {}
        for key, settings in raw.items():
            model_cls = cls._SOURCE_TYPES.get(key)
            if model_cls is None:
                known = ", ".join(sorted(cls._SOURCE_TYPES))
                raise ConfigError(f"{path}: unknown source {key!r}; known: {known}")
            if not isinstance(settings, dict):
                raise ConfigError(f"{path}: source {key!r} must be a mapping")
            sources[key] = cls._parse_nested(
                _Block(settings, f"source {key}", path), model_cls
            )
        return sources

    @classmethod
    def _format_errors(cls, exc: ValidationError) -> str:
        """Render pydantic errors as one line per field."""
        return "\n".join(
            f"  {'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
