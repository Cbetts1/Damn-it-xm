# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Resource Ledger — immutable accounting records for all task execution."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.resources.ledger")


@dataclass
class LedgerEntry:
    """An accounting record for a single task execution."""

    task_id: str
    user_id: Optional[str]
    task_name: str
    cpu_ms: float
    ram_mb_peak: float
    started_at: str
    finished_at: Optional[str]
    status: str

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "task_name": self.task_name,
            "cpu_ms": round(self.cpu_ms, 2),
            "ram_mb_peak": round(self.ram_mb_peak, 2),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
        }


class ResourceLedger:
    """
    Thread-safe accounting ledger for all task executions.

    Keeps records in memory (evict oldest when over cap) and exposes
    summary statistics for cost/capacity analysis.
    """

    _MAX_ENTRIES: int = 4096

    def __init__(self) -> None:
        self._entries: dict[str, LedgerEntry] = {}
        self._order: list[str] = []           # insertion order for eviction
        self._lock = threading.Lock()
        _logger.info("ResourceLedger initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_start(
        self,
        task_id: str,
        task_name: str,
        user_id: Optional[str] = None,
        ram_mb: float = 0.0,
    ) -> None:
        """Begin an accounting record for *task_id*."""
        entry = LedgerEntry(
            task_id=task_id,
            user_id=user_id,
            task_name=task_name,
            cpu_ms=0.0,
            ram_mb_peak=ram_mb,
            started_at=utcnow(),
            finished_at=None,
            status="running",
        )
        with self._lock:
            self._entries[task_id] = entry
            self._order.append(task_id)
            # Evict oldest if over cap
            while len(self._order) > self._MAX_ENTRIES:
                old = self._order.pop(0)
                self._entries.pop(old, None)

    def record_finish(
        self,
        task_id: str,
        status: str,
        cpu_ms: float = 0.0,
    ) -> None:
        """Finalise the accounting record for *task_id*."""
        with self._lock:
            entry = self._entries.get(task_id)
        if entry is None:
            _logger.debug("Ledger: no open record for task %s", task_id)
            return
        entry.finished_at = utcnow()
        entry.status = status
        entry.cpu_ms = cpu_ms

    def get_entry(self, task_id: str) -> Optional[dict]:
        """Return the ledger record for *task_id* as a dict, or None."""
        with self._lock:
            entry = self._entries.get(task_id)
        return entry.to_dict() if entry else None

    def list_entries(self, limit: int = 100) -> List[dict]:
        """Return the most recent *limit* ledger entries (newest first)."""
        with self._lock:
            order = list(self._order)
            entries = dict(self._entries)
        recent = order[-limit:]
        recent.reverse()
        return [entries[tid].to_dict() for tid in recent if tid in entries]

    def summary(self) -> dict:
        """Return aggregate statistics across all records."""
        with self._lock:
            all_entries = list(self._entries.values())
        by_status: dict[str, int] = {}
        total_cpu_ms = 0.0
        for e in all_entries:
            by_status[e.status] = by_status.get(e.status, 0) + 1
            total_cpu_ms += e.cpu_ms
        return {
            "total_tasks": len(all_entries),
            "total_cpu_ms": round(total_cpu_ms, 2),
            "by_status": by_status,
        }
