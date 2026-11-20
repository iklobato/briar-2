"""Error hierarchy for briar-2.

All user-visible errors inherit from CliError so the CLI can report
them cleanly without leaking internal exceptions.
"""

from __future__ import annotations


class CliError(Exception):
    """Base class for all briar-2 user-facing errors."""


class ConfigError(CliError):
    """Configuration file or environment is invalid."""


class AuthError(CliError):
    """Required credential is missing or expired."""


class SourceError(CliError):
    """A polling source failed to fetch events."""


class ActionError(CliError):
    """An action executor failed."""


class LockError(CliError):
    """Resource lock could not be acquired."""
