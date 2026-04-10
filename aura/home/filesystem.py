# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa HOME — Filesystem Overlay
================================
The HOME filesystem provides an isolated, writable overlay on top of the
ROOT filesystem.  It is the directory tree that userland processes see.

Structure
---------
::

    $HOME_DIR/
    ├── bin/       — user binaries and scripts
    ├── etc/       — HOME-local configuration
    ├── tmp/       — ephemeral temporary files (cleared on unmount)
    ├── var/       — variable data (logs, run files)
    │   ├── log/
    │   └── run/
    ├── home/      — per-user home directories
    │   └── aura/  — the default AURA operator account
    └── opt/       — optional/third-party packages

All paths are scoped under a configurable base directory so the HOME
filesystem is fully portable (SD-card style).
"""

from __future__ import annotations

import os
import shutil
from typing import List

from aura.utils import get_logger

_logger = get_logger("aura.home.filesystem")

_HOME_DIRS = [
    "bin",
    "etc",
    "tmp",
    "var/log",
    "var/run",
    "home/aura",
    "opt",
]


class HomeFilesystem:
    """
    HOME filesystem overlay manager.

    Parameters
    ----------
    base_dir:
        Root directory for the HOME filesystem tree.
    """

    def __init__(self, base_dir: str) -> None:
        self._base = base_dir
        _logger.info("HomeFilesystem: base=%s", base_dir)

    @property
    def base_dir(self) -> str:
        return self._base

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def mount(self) -> None:
        """Create the HOME directory tree (idempotent)."""
        for rel in _HOME_DIRS:
            os.makedirs(os.path.join(self._base, rel), exist_ok=True)
        _logger.info("HomeFilesystem: mounted (%s)", self._base)

    def unmount(self) -> None:
        """Flush ephemeral files (tmp/) on unmount."""
        tmp_dir = os.path.join(self._base, "tmp")
        try:
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir)
                os.makedirs(tmp_dir, exist_ok=True)
        except OSError as exc:
            _logger.warning("HomeFilesystem: tmp flush error: %s", exc)
        _logger.info("HomeFilesystem: unmounted")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def path(self, *parts: str) -> str:
        """Return the absolute path of a HOME-relative path."""
        rel = os.path.join(*parts) if parts else ""
        full = os.path.normpath(os.path.join(self._base, rel))
        # Security: prevent path traversal outside HOME
        if not full.startswith(os.path.normpath(self._base)):
            raise ValueError(f"Path traversal outside HOME: {rel!r}")
        return full

    def exists(self, *parts: str) -> bool:
        return os.path.exists(self.path(*parts))

    def ls(self, *parts: str) -> List[str]:
        """List directory contents."""
        p = self.path(*parts)
        if not os.path.isdir(p):
            return []
        return sorted(os.listdir(p))

    def read(self, *parts: str) -> str:
        """Read a text file within HOME."""
        with open(self.path(*parts), "r", encoding="utf-8") as fh:
            return fh.read()

    def write(self, content: str, *parts: str) -> None:
        """Write a text file within HOME."""
        full = self.path(*parts)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)

    def delete(self, *parts: str) -> bool:
        """
        Delete a file or directory within HOME.

        Returns ``True`` if the path existed and was removed, ``False``
        if it did not exist.

        Raises
        ------
        ValueError
            On path-traversal attempts.
        OSError
            If the underlying remove operation fails.
        """
        full = self.path(*parts)
        if not os.path.exists(full):
            return False
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
        _logger.info("HomeFilesystem: deleted %s", full)
        return True

    def metrics(self) -> dict:
        try:
            total, used, free = shutil.disk_usage(self._base)
        except OSError:
            total, used, free = 0, 0, 0
        return {
            "base_dir": self._base,
            "disk_total_bytes": total,
            "disk_used_bytes": used,
            "disk_free_bytes": free,
        }
