"""Tests for the source pollers."""

from __future__ import annotations

from briar2.sources.github import GitHubConfig, GitHubSource
from briar2.sources.gitlab import GitLabConfig, GitLabSource
from briar2.sources.jira import JiraConfig, JiraSource

_GITLAB_SECONDS = 90
_JIRA_SECONDS = 300
_GITHUB_SECONDS = 120
_SELF_HOSTED_GITLAB = "https://gitlab.gatik.com"
_GITLAB_PROJECT = "gatik/ai-infra"
_ENTERPRISE_GITHUB = "https://ghe.example.com/api/v3"
_GITHUB_REPO = "acme/tool"


def test_the_gitlab_url_points_at_the_configured_instance() -> None:
    """A self-hosted GitLab gets its own API URL."""
    config = GitLabConfig(
        token_env="GITLAB_TOKEN",
        project=_GITLAB_PROJECT,
        url=_SELF_HOSTED_GITLAB,
        poll_every="90s",
    )

    url = config.merge_requests_url()

    assert url == (
        "https://gitlab.gatik.com/api/v4/projects/gatik%2Fai-infra/merge_requests"
    )


def test_the_github_url_points_at_the_configured_api() -> None:
    """A GitHub Enterprise base URL is used as it is."""
    config = GitHubConfig(
        token_env="GITHUB_TOKEN",
        repos=[_GITHUB_REPO],
        url=_ENTERPRISE_GITHUB,
        poll_every="2m",
    )

    assert config.pulls_url(_GITHUB_REPO) == (
        "https://ghe.example.com/api/v3/repos/acme/tool/pulls"
    )


def test_the_gitlab_poll_interval_comes_from_the_config() -> None:
    """The GitLab source polls at the interval the config asks for."""
    source = GitLabSource(
        GitLabConfig(
            token_env="GITLAB_TOKEN",
            project=_GITLAB_PROJECT,
            url=_SELF_HOSTED_GITLAB,
            poll_every="90s",
        )
    )

    assert source.poll_every_seconds == _GITLAB_SECONDS


def test_the_jira_poll_interval_comes_from_the_config() -> None:
    """The Jira source polls at the interval the config asks for."""
    source = JiraSource(
        JiraConfig(
            token_env="JIRA_TOKEN",
            jql="project = GAIT",
            url="https://gatik-engineering.atlassian.net",
            poll_every="5m",
        )
    )

    assert source.poll_every_seconds == _JIRA_SECONDS


def test_the_github_poll_interval_comes_from_the_config() -> None:
    """The GitHub source polls at the interval the config asks for."""
    source = GitHubSource(
        GitHubConfig(
            token_env="GITHUB_TOKEN",
            repos=[_GITHUB_REPO],
            url=_ENTERPRISE_GITHUB,
            poll_every="2m",
        )
    )

    assert source.poll_every_seconds == _GITHUB_SECONDS
