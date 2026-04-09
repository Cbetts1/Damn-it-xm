# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Virtual RAM — an in-memory resource pool with task-scoped allocation."""

from __future__ import annotations

import threading
from typing import Dict, Optional

from aura.utils import get_logger, EVENT_BUS
from aura.resources.model import ResourceSlot

_logger = get_logger("aura.resources.ram")


class VirtualRAM:
    """
    Virtual RAM pool for the AURa AI OS.

    Tracks per-task allocations so that RAM is released automatically
    when tasks complete or fail (via EventBus events).
    """

    def __init__(self, total_mb: float = 2048.0) -> None:
        self._slot = ResourceSlot(name="ram", total=total_mb, unit="MB")
        self._allocations: Dict[str, float] = {}   # task_id → mb
        self._lock = threading.Lock()

        # Auto-release on CPU and scheduler events
        for event in (
            "cpu.task.completed",
            "cpu.task.failed",
            "scheduler.task.completed",
            "scheduler.task.failed",
        ):
            EVENT_BUS.subscribe(event, self._on_task_done)

        _logger.info("VirtualRAM initialised: %.0f MB total", total_mb)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allocate(self, task_id: str, mb: float) -> bool:
        """Allocate *mb* MB for *task_id*. Returns False if insufficient RAM."""
        if mb <= 0:
            return True  # nothing requested — always succeeds
        with self._lock:
            if task_id in self._allocations:
                _logger.debug("RAM: task %s already has an allocation", task_id)
                return True
            if not self._slot.allocate(mb):
                _logger.warning(
                    "RAM: cannot allocate %.1f MB for %s — available=%.1f MB",
                    mb,
                    task_id,
                    self._slot.available,
                )
                return False
            self._allocations[task_id] = mb
            _logger.debug("RAM: allocated %.1f MB for task %s", mb, task_id)
            return True

    def release(self, task_id: str) -> None:
        """Release the RAM allocation held by *task_id* (no-op if none)."""
        with self._lock:
            mb = self._allocations.pop(task_id, None)
        if mb is not None:
            self._slot.release(mb)
            _logger.debug("RAM: released %.1f MB for task %s", mb, task_id)

    def usage(self) -> dict:
        """Return a usage snapshot."""
        snap = self._slot.snapshot()
        return {
            "total_mb": snap["total"],
            "used_mb": round(snap["allocated"], 2),
            "free_mb": round(snap["available"], 2),
            "utilisation_pct": snap["utilisation_pct"],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_task_done(self, event_type: str, payload) -> None:
        if isinstance(payload, dict):
            task_id = payload.get("task_id")
            if task_id:
                self.release(task_id)
