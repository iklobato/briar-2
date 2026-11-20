"""Build source pollers from a company config.

Keeps the orchestrator focused on the loop: the factory owns the
mapping from a `sources` block to concrete pollers.
"""

from __future__ import annotations

from typing import Any

from briar2.config import (
    GitHubSourceConfig,
    GitLabSourceConfig,
    JiraSourceConfig,
    SlackSourceConfig,
)
from briar2.sources.base import Source


class SourceFactory:
    """Turn the `sources` block of a company config into pollers."""

    def build(self, sources: dict[str, Any]) -> list[Source]:
        """Build one poller per configured source, skipping unknown blocks."""
        built: list[Source] = []
        for key, cfg in sources.items():
            source = self._make(key, cfg)
            if source is not None:
                built.append(source)
        return built

    def _make(self, key: str, cfg: Any) -> Source | None:
        if key == "slack" and isinstance(cfg, SlackSourceConfig):
            return self._slack(cfg)
        if key == "gitlab" and isinstance(cfg, GitLabSourceConfig):
            return self._gitlab(cfg)
        if key == "github" and isinstance(cfg, GitHubSourceConfig):
            return self._github(cfg)
        if key == "jira" and isinstance(cfg, JiraSourceConfig):
            return self._jira(cfg)
        return None

    def _slack(self, cfg: SlackSourceConfig) -> Source:
        from briar2.sources.slack import SlackSource

        return SlackSource(
            bot_token_env=cfg.bot_token_env,
            channels=cfg.channels,
            poll_every=cfg.poll_every,
        )

    def _gitlab(self, cfg: GitLabSourceConfig) -> Source:
        from briar2.sources.gitlab import GitLabSource

        return GitLabSource(
            token_env=cfg.token_env,
            project=cfg.project,
            poll_every=cfg.poll_every,
        )

    def _github(self, cfg: GitHubSourceConfig) -> Source:
        from briar2.sources.github import GitHubSource

        return GitHubSource(
            token_env=cfg.token_env,
            repos=cfg.repos,
            poll_every=cfg.poll_every,
        )

    def _jira(self, cfg: JiraSourceConfig) -> Source:
        from briar2.sources.jira import JiraSource, _JiraConfig

        return JiraSource(
            _JiraConfig(
                token_env=cfg.token_env,
                jql=cfg.jql,
                url=cfg.url,
                poll_every=cfg.poll_every,
            )
        )
