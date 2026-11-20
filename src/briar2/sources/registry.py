"""Registry of the source pollers available to a company.

The orchestrator only knows `SourceRegistry.build(name, cfg)`; adding a
new source type means adding a method here.
"""

from __future__ import annotations

from typing import Callable

from briar2.config import (
    GitHubSourceConfig,
    GitLabSourceConfig,
    JiraSourceConfig,
    SlackSourceConfig,
)
from briar2.sources.base import Source
from pydantic import BaseModel


class SourceRegistry:
    """Build source pollers from config models."""

    _builders: dict[str, Callable[[BaseModel], Source]] = {}

    @classmethod
    def register(cls, name: str) -> Callable:
        """Register a builder method under a name."""

        def decorator(builder: Callable) -> Callable:
            cls._builders[name] = builder
            return builder

        return decorator

    @classmethod
    def build(cls, name: str, cfg: BaseModel) -> Source:
        """Build a source by name."""
        builder = cls._builders.get(name)
        if builder is None:
            raise KeyError(f"unknown source type: {name!r}")
        return builder(cfg)

    @staticmethod
    def _build_slack(cfg: BaseModel) -> Source:
        from briar2.sources.slack import SlackConfig, SlackSource

        scfg = SlackSourceConfig.model_validate(cfg.model_dump())
        return SlackSource(
            SlackConfig(
                poll_every=scfg.poll_every,
                bot_token_env=scfg.bot_token_env,
                channels=scfg.channels,
            )
        )

    @staticmethod
    def _build_gitlab(cfg: BaseModel) -> Source:
        from briar2.sources.gitlab import GitLabConfig, GitLabSource

        gcfg = GitLabSourceConfig.model_validate(cfg.model_dump())
        return GitLabSource(
            GitLabConfig(
                poll_every=gcfg.poll_every,
                token_env=gcfg.token_env,
                project=gcfg.project,
                url=gcfg.url,
            )
        )

    @staticmethod
    def _build_github(cfg: BaseModel) -> Source:
        from briar2.sources.github import GitHubConfig, GitHubSource

        gcfg = GitHubSourceConfig.model_validate(cfg.model_dump())
        return GitHubSource(
            GitHubConfig(
                poll_every=gcfg.poll_every,
                token_env=gcfg.token_env,
                repos=gcfg.repos,
                url=gcfg.url,
            )
        )

    @staticmethod
    def _build_jira(cfg: BaseModel) -> Source:
        from briar2.sources.jira import JiraConfig, JiraSource

        jcfg = JiraSourceConfig.model_validate(cfg.model_dump())
        return JiraSource(
            JiraConfig(
                poll_every=jcfg.poll_every,
                token_env=jcfg.token_env,
                jql=jcfg.jql,
                url=jcfg.url,
            )
        )


# Register all builders
SourceRegistry._builders = {
    "slack": SourceRegistry._build_slack,
    "gitlab": SourceRegistry._build_gitlab,
    "github": SourceRegistry._build_github,
    "jira": SourceRegistry._build_jira,
}
