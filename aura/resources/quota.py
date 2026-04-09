# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Quota Enforcer — per-user resource limits with soft enforcement."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.resources.ram import VirtualRAM

_logger = get_logger("aura.resources.quota")


@dataclass
class Quota:
    """Resource quota for a single user."""

    user_id: str = "system"
    max_cpu_cores: float = 0.0   # 0 = unlimited
    max_ram_mb: float = 0.0      # 0 = unlimited
    max_tasks: int = 0            # 0 = unlimited


class QuotaEnforcer:
    """
    Checks whether a user's resource request would exceed their quota.

    In vNext mode the check is *soft* — a quota violation is logged as a
    warning but does not block task submission (returns ``(False, reason)``
    so callers can log/escalate as they see fit).
    """

    def __init__(self, ram: "VirtualRAM") -> None:
        self._ram = ram
        self._quotas: Dict[str, Quota] = {}
        self._active_tasks: Dict[str, int] = {}  # user_id → running count
        self._lock = threading.Lock()
        _logger.info("QuotaEnforcer initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_quota(self, user_id: str, quota: Quota) -> None:
        """Register or update the quota for *user_id*."""
        with self._lock:
            self._quotas[user_id] = quota
        _logger.info("Quota set for user %s: %s", user_id, quota)

    def increment_tasks(self, user_id: str) -> None:
        """Increment the active task counter for *user_id*."""
        if user_id is None:
            return
        with self._lock:
            self._active_tasks[user_id] = self._active_tasks.get(user_id, 0) + 1

    def decrement_tasks(self, user_id: str) -> None:
        """Decrement the active task counter for *user_id*."""
        if user_id is None:
            return
        with self._lock:
            current = self._active_tasks.get(user_id, 0)
            self._active_tasks[user_id] = max(0, current - 1)

    def check(
        self, user_id: str, ram_mb: float = 0.0
    ) -> Tuple[bool, str]:
        """
        Check whether a new task from *user_id* requesting *ram_mb* MB would
        violate their quota.

        Returns ``(True, "")`` if within limits, ``(False, reason)`` if exceeded.
        """
        with self._lock:
            quota = self._quotas.get(user_id)
            active = self._active_tasks.get(user_id, 0)

        if quota is None:
            return True, ""

        # Check task count
        if quota.max_tasks > 0 and active >= quota.max_tasks:
            reason = (
                f"user {user_id!r} task quota exceeded: "
                f"{active}/{quota.max_tasks} active tasks"
            )
            _logger.warning("Quota check failed: %s", reason)
            return False, reason

        # Check RAM
        if quota.max_ram_mb > 0 and ram_mb > quota.max_ram_mb:
            reason = (
                f"user {user_id!r} RAM quota exceeded: "
                f"requested {ram_mb:.1f} MB > limit {quota.max_ram_mb:.1f} MB"
            )
            _logger.warning("Quota check failed: %s", reason)
            return False, reason

        # Check available RAM against system pool
        usage = self._ram.usage()
        if usage["free_mb"] < ram_mb:
            reason = (
                f"insufficient RAM: requested {ram_mb:.1f} MB, "
                f"available {usage['free_mb']:.1f} MB"
            )
            _logger.warning("Quota check failed: %s", reason)
            return False, reason

        return True, ""
