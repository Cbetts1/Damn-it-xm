# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Kernel — System Log Service
==================================
Centralised, thread-safe in-memory log store for kernel and subsystem
events.  Convenience helpers (``info``, ``warn``, ``error``) mirror the
standard logging API.  Rolling buffer caps at 10 000 entries.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.kernel.syslog")

_MAX_ENTRIES = 10_000


class SyslogService:
    """
    In-memory system log with structured entries and query support.

    Entries are dicts with keys:
        ``timestamp``, ``level``, ``source``, ``message``.

    The buffer rolls at :data:`_MAX_ENTRIES`; the oldest entry is
    discarded when the limit is exceeded.
    """

    def __init__(self) -> None:
        self._entries: List[dict] = []
        self._lock = threading.Lock()
        _logger.info("SyslogService initialised")

    # ------------------------------------------------------------------
    # Core write API
    # ------------------------------------------------------------------

    def log(self, level: str, source: str, message: str) -> None:
        """
        Append a structured log entry.

        Parameters
        ----------
        level:
            Severity label (e.g. ``"INFO"``, ``"WARN"``, ``"ERROR"``).
        source:
            Component or subsystem that generated the entry.
        message:
            Human-readable message.
        """
        entry: dict = {
            "timestamp": utcnow(),
            "level": level.upper(),
            "source": source,
            "message": message,
        }
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > _MAX_ENTRIES:
                self._entries.pop(0)
        _logger.debug("syslog [%s] %s: %s", level, source, message)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def info(self, source: str, message: str) -> None:
        """Append an INFO-level entry."""
        self.log("INFO", source, message)

    def warn(self, source: str, message: str) -> None:
        """Append a WARN-level entry."""
        self.log("WARN", source, message)

    def error(self, source: str, message: str) -> None:
        """Append an ERROR-level entry."""
        self.log("ERROR", source, message)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def query(
        self,
        level: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        """
        Retrieve log entries with optional filters.

        Parameters
        ----------
        level:
            If given, only entries whose ``level`` matches (case-insensitive).
        source:
            If given, only entries whose ``source`` matches.
        limit:
            Maximum number of entries to return (most-recent first).

        Returns
        -------
        List[dict]
            Matching entries in reverse-chronological order.
        """
        with self._lock:
            entries = list(self._entries)

        if level is not None:
            level_upper = level.upper()
            entries = [e for e in entries if e["level"] == level_upper]
        if source is not None:
            entries = [e for e in entries if e["source"] == source]

        return entries[-limit:][::-1]

    def metrics(self) -> Dict[str, int]:
        """Return entry counts grouped by level."""
        counts: Dict[str, int] = {}
        with self._lock:
            for entry in self._entries:
                lvl = entry["level"]
                counts[lvl] = counts.get(lvl, 0) + 1
        counts["total"] = sum(counts.values())
        return counts
