"""File-based resource lock using fcntl.flock.

One lock file per resource key (D41). Acquire with timeout (D43),
release on explicit call. No cross-company locks (D52) — each
process manages its own lock_root.
"""

from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path

_BACKOFF_BASE = 0.05  # 50ms initial backoff (D43)
_BACKOFF_MAX = 5.0  # 5s max backoff
_BACKOFF_FACTOR = 2  # exponential growth of the backoff
_DEFAULT_TIMEOUT = 5.0  # D43: 5s acquire timeout
_LOCK_FILE_MODE = 0o644


class ResourceLock:
    """flock-based resource lock.

    Usage::

        lock = ResourceLock.from_root("/tmp/locks")
        if lock.acquire("mr/gitlab/123"):
            try:
                do_work()
            finally:
                lock.release("mr/gitlab/123")
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._held: dict[str, int] = {}  # resource → fd

    @classmethod
    def from_root(cls, lock_root: str) -> ResourceLock:
        """Create the lock directory and return a lock rooted there."""
        root = Path(lock_root).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return cls(root)

    def acquire(self, resource: str, timeout: float = _DEFAULT_TIMEOUT) -> bool:
        """Acquire a resource lock. Returns True on success, False on timeout (D43)."""
        if resource in self._held:
            return True  # already held by this instance
        self._root.mkdir(parents=True, exist_ok=True)
        lock_path = self._root / self._safe_name(resource)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, _LOCK_FILE_MODE)
        if not self._wait_for(fd, timeout):
            os.close(fd)
            return False
        self._held[resource] = fd
        return True

    def release(self, resource: str) -> None:
        """Release a held resource lock."""
        fd = self._held.pop(resource, None)
        if fd is None:
            return
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            os.close(fd)

    def held(self) -> list[str]:
        """Return list of currently held resource keys."""
        return list(self._held.keys())

    def _wait_for(self, fd: int, timeout: float) -> bool:
        """Try to flock the descriptor until the deadline. False on timeout."""
        deadline = time.monotonic() + timeout
        backoff = _BACKOFF_BASE
        while True:
            if self._try_lock(fd):
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(backoff, remaining))
            backoff = min(backoff * _BACKOFF_FACTOR, _BACKOFF_MAX)

    def _try_lock(self, fd: int) -> bool:
        """Try one non-blocking flock. False when someone else holds it."""
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    def _safe_name(self, resource: str) -> str:
        """Convert a resource key to a safe filename."""
        return resource.replace("/", "_").replace(":", "_") + ".lock"
