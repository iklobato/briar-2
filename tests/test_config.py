"""Tests for the company config loader."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from briar2.config import CompanyConfigLoader
from briar2.errors import ConfigError

_EXPECTED_CAP = 2
_FULL_CONFIG = """
company: acme
cap: 2
sources:
  slack:
    channels: [C123]
    poll_every: 30s
actions:
  slack_draft: true
  gitlab_approve: true
paths:
  knowledge_root: /tmp/knowledge
"""
_UNKNOWN_SOURCE_CONFIG = """
company: acme
sources:
  teams:
    channels: [T1]
"""
_BAD_INTERVAL_CONFIG = """
company: acme
sources:
  slack:
    poll_every: 5x
"""
_UNKNOWN_KEY_CONFIG = """
company: acme
unexpected_key: true
"""
_NO_COMPANY_CONFIG = """
cap: 2
"""
_SELF_HOSTED_GITLAB_CONFIG = """
company: acme
sources:
  gitlab:
    project: gatik/ai-infra
    url: https://gitlab.gatik.com
"""
_GITLAB_CONFIG = """
company: acme
sources:
  gitlab:
    project: gatik/ai-infra
"""
_DEFAULT_GITLAB_URL = "https://gitlab.com"


def test_loads_a_full_config(config_path: Callable[[str], Path]) -> None:
    """A complete config parses into its blocks."""
    path = config_path(_FULL_CONFIG)

    config = CompanyConfigLoader.load(path)

    assert config.company == "acme"
    assert config.cap == _EXPECTED_CAP
    assert config.actions.gitlab_approve is True


def test_loads_the_source_blocks(config_path: Callable[[str], Path]) -> None:
    """The slack source keeps its channels and its interval."""
    path = config_path(_FULL_CONFIG)

    config = CompanyConfigLoader.load(path)

    assert config.sources["slack"].channels == ["C123"]


def test_rejects_an_unknown_source(config_path: Callable[[str], Path]) -> None:
    """An unknown source names the sources that exist."""
    path = config_path(_UNKNOWN_SOURCE_CONFIG)

    with pytest.raises(ConfigError) as failure:
        CompanyConfigLoader.load(path)

    assert "unknown source 'teams'" in str(failure.value)


def test_rejects_a_bad_poll_interval(config_path: Callable[[str], Path]) -> None:
    """A bad interval is reported with the accepted forms."""
    path = config_path(_BAD_INTERVAL_CONFIG)

    with pytest.raises(ConfigError) as failure:
        CompanyConfigLoader.load(path)

    assert "bad interval '5x'" in str(failure.value)


def test_rejects_an_unknown_top_level_key(config_path: Callable[[str], Path]) -> None:
    """The config is strict, so an unknown key is an error."""
    path = config_path(_UNKNOWN_KEY_CONFIG)

    with pytest.raises(ConfigError) as failure:
        CompanyConfigLoader.load(path)

    assert "unexpected_key" in str(failure.value)


def test_rejects_a_missing_company(config_path: Callable[[str], Path]) -> None:
    """The company name is required."""
    path = config_path(_NO_COMPANY_CONFIG)

    with pytest.raises(ConfigError) as failure:
        CompanyConfigLoader.load(path)

    assert "company" in str(failure.value)


def test_the_gitlab_url_defaults_to_gitlab_com(
    config_path: Callable[[str], Path],
) -> None:
    """Without a url, the source talks to gitlab.com."""
    path = config_path(_GITLAB_CONFIG)

    config = CompanyConfigLoader.load(path)

    assert config.sources["gitlab"].url == _DEFAULT_GITLAB_URL


def test_the_gitlab_instance_url_can_be_overridden(
    config_path: Callable[[str], Path],
) -> None:
    """A self-hosted GitLab only needs its url in the config."""
    path = config_path(_SELF_HOSTED_GITLAB_CONFIG)

    config = CompanyConfigLoader.load(path)

    assert config.sources["gitlab"].url == "https://gitlab.gatik.com"
