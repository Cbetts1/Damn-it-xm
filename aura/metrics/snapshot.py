# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa SystemSnapshot — a single consistent read of all resource states."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aura.metrics.health import HealthProbe
from aura.utils import get_logger, utcnow

if TYPE_CHECKING:
    from aura.os_core.ai_os import AIOS

_logger = get_logger("aura.metrics.snapshot")

_probe = HealthProbe()


class SystemSnapshot:
    """Takes a consistent, point-in-time snapshot of all AIOS subsystems."""

    def take(self, aios_ref: "AIOS") -> dict:
        snapshot: dict[str, Any] = {"timestamp": utcnow()}

        # CPU
        try:
            cpu = aios_ref._cpu
            snapshot["cpu"] = cpu.metrics() if cpu else {}
        except Exception:
            snapshot["cpu"] = {}

        # RAM
        try:
            ram = aios_ref._ram
            snapshot["ram"] = ram.usage() if ram else {}
        except Exception:
            snapshot["ram"] = {}

        # Cloud
        try:
            cloud = aios_ref._cloud
            snapshot["cloud"] = cloud.metrics() if cloud else {}
        except Exception:
            snapshot["cloud"] = {}

        # Server
        try:
            srv = aios_ref._server
            snapshot["server"] = srv.metrics() if srv else {}
        except Exception:
            snapshot["server"] = {}

        # Scheduler
        try:
            sched = aios_ref._scheduler
            snapshot["scheduler"] = sched.metrics() if sched else {}
        except Exception:
            snapshot["scheduler"] = {}

        # Health
        try:
            snapshot["health"] = _probe.check_all(snapshot)
        except Exception:
            snapshot["health"] = {}

        return snapshot
