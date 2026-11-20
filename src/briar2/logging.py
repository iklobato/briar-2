"""Logging setup for briar-2.

Uses structlog for structured logging with a rotating file handler.
stdlib logging is bridged in so existing `logging.getLogger()` calls work.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys

import structlog
from structlog.stdlib import BoundLogger


_LOG_DIR = "~/.cache/briar/logs"
_LOG_FILE = "briar2.log"
_MAX_BYTES = 10_000_000
_BACKUP_COUNT = 5


def _configure_root() -> None:
    """Configure the stdlib root logger once."""
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    log_dir = os.path.expanduser(_LOG_DIR)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, _LOG_FILE)

    root.setLevel(logging.DEBUG)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(file_handler)

    if os.environ.get("BRIAR_VERBOSE"):
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.DEBUG)
        stderr_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        root.addHandler(stderr_handler)


class BriarLogger:
    """Return a structlog logger backed by a rotating file."""

    @classmethod
    def build(cls, name: str) -> BoundLogger:
        """Return a structured logger for the given component name."""
        _configure_root()
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        return structlog.get_logger(f"briar2.{name}")
