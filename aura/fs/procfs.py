# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Filesystem Layer — ProcFS
==============================
A virtual /proc-style filesystem backed by registered callables.
Each provider is a zero-argument (or context-free) callable that returns
the string content for its registered path.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.fs.procfs")


class ProcFS:
    """
    Virtual /proc filesystem for AURa OS.

    Providers are plain callables (``() -> str``) registered against a
    proc path.  Reading a path invokes its provider and returns the
    resulting string.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, Callable[[], str]] = {}
        self._register_defaults()
        _logger.info("ProcFS initialised with %d default providers", len(self._providers))

    # ------------------------------------------------------------------
    # Default built-in providers
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:
        self.register_provider("/proc/version", lambda: "AURa OS 2.0.0")
        self.register_provider("/proc/uptime",  lambda: f"uptime since {utcnow()}")
        self.register_provider("/proc/cpuinfo", lambda: "AURa Virtual CPU")
        self.register_provider("/proc/meminfo", lambda: "AURa Virtual Memory")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_provider(self, proc_path: str, fn: Callable[[], str]) -> None:
        """
        Register *fn* as the data provider for *proc_path*.

        Any previously registered provider for the same path is replaced.
        """
        self._providers[proc_path] = fn
        _logger.debug("register_provider: '%s' registered", proc_path)

    def read(self, proc_path: str) -> Optional[str]:
        """
        Invoke the provider for *proc_path* and return its output.

        Returns *None* if no provider is registered for that path.
        """
        provider = self._providers.get(proc_path)
        if provider is None:
            _logger.debug("read: no provider for '%s'", proc_path)
            return None
        try:
            result = provider()
            _logger.debug("read: '%s' -> %r", proc_path, result)
            return result
        except Exception as exc:  # providers are user-supplied; catch all to stay stable
            _logger.error("read: provider for '%s' raised: %s", proc_path, exc)
            return None

    def list_entries(self) -> List[str]:
        """Return a sorted list of all registered proc paths."""
        return sorted(self._providers.keys())
