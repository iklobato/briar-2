"""Logging setup for briar-2.

Rotating file logger for the long-running daemon (serve loop).
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


class DaemonLogger:
    """Rotating file logger for the briar2 daemon (UTC timestamps)."""

    _LOG_DIR = "~/.cache/briar/logs"
    _LOG_FILE = "briar2.log"
    _MAX_BYTES = 10_000_000
    _BACKUP_COUNT = 3
    _FILE_FORMAT = "%(asctime)sZ %(levelname)-5s %(name)s: %(message)s"
    _STDERR_FORMAT = "[%(levelname)s] %(message)s"

    def __init__(self, name: str) -> None:
        self._name = name

    def build(self) -> logging.Logger:
        """Return the logger: rotating file always, stderr when BRIAR_VERBOSE is set."""
        log_dir = os.path.expanduser(self._LOG_DIR)
        os.makedirs(log_dir, exist_ok=True)
        logger = logging.getLogger(f"briar2.{self._name}")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(self._file_handler(log_dir))
        if os.environ.get("BRIAR_VERBOSE"):
            logger.addHandler(self._stderr_handler())
        return logger

    def _file_handler(self, log_dir: str) -> RotatingFileHandler:
        """Build the rotating file handler."""
        handler = RotatingFileHandler(
            os.path.join(log_dir, self._LOG_FILE),
            maxBytes=self._MAX_BYTES,
            backupCount=self._BACKUP_COUNT,
        )
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(self._FILE_FORMAT))
        return handler

    def _stderr_handler(self) -> logging.StreamHandler:
        """Build the stderr handler used when BRIAR_VERBOSE is set."""
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(self._STDERR_FORMAT))
        return handler
