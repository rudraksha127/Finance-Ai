"""Filesystem lock preventing concurrent pipeline runs (P01 section 32).

Two pipeline runs for the same (instrument, interval) must never overlap.
The simplest reliable mechanism for the file-based MVP is an exclusive
lock file created with ``O_CREAT | O_EXCL`` — atomic on every platform,
no new dependencies, no advisory-lock semantics to get wrong.
"""

from __future__ import annotations

import os
from pathlib import Path


class PipelineLock:
    """Exclusive lock file for one (instrument, interval)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def acquire(self, *, nonblocking: bool = True) -> bool:
        """Create the lock file atomically. Returns True when acquired."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(self.path, flags)
        except FileExistsError:
            if nonblocking:
                return False
            # Blocking path: wait for release (bounded by caller).
            while True:
                try:
                    fd = os.open(self.path, flags)
                    break
                except FileExistsError:
                    import time

                    time.sleep(0.25)
        os.write(fd, b"locked\n")
        os.close(fd)
        return True

    def release(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> PipelineLock:  # noqa: PYI034 — returns self by design
        if not self.acquire():
            raise RuntimeError(f"pipeline lock already held: {self.path}")
        return self

    def __exit__(self, *exc) -> None:
        self.release()
