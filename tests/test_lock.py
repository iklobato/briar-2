"""Tests for the flock-based resource lock."""

from __future__ import annotations

from pathlib import Path

from briar2.lock import ResourceLock

_SHORT_TIMEOUT = 0.2
_RESOURCE = "mr/gitlab/123"


def test_acquire_holds_the_resource(tmp_path: Path) -> None:
    """A held lock is listed until it is released."""
    lock = ResourceLock.from_root(str(tmp_path / "locks"))

    assert lock.acquire(_RESOURCE) is True
    assert lock.held() == [_RESOURCE]


def test_release_frees_the_resource(tmp_path: Path) -> None:
    """After the release the lock is not held anymore."""
    lock = ResourceLock.from_root(str(tmp_path / "locks"))
    lock.acquire(_RESOURCE)

    lock.release(_RESOURCE)

    assert lock.held() == []


def test_another_lock_times_out(tmp_path: Path) -> None:
    """A second lock on the same resource gives up after the timeout."""
    root = str(tmp_path / "locks")
    holder = ResourceLock.from_root(root)
    holder.acquire(_RESOURCE)
    other = ResourceLock.from_root(root)

    assert other.acquire(_RESOURCE, timeout=_SHORT_TIMEOUT) is False


def test_the_same_lock_can_be_taken_twice(tmp_path: Path) -> None:
    """Re-acquiring a lock this instance already holds succeeds."""
    lock = ResourceLock.from_root(str(tmp_path / "locks"))
    lock.acquire(_RESOURCE)

    assert lock.acquire(_RESOURCE) is True


def test_releasing_an_unknown_resource_is_harmless(tmp_path: Path) -> None:
    """Releasing a lock that was never taken does nothing."""
    lock = ResourceLock.from_root(str(tmp_path / "locks"))

    lock.release(_RESOURCE)

    assert lock.held() == []
