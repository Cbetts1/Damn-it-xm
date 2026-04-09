# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa HealthProbe — threshold-based subsystem health checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.metrics.health")


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class SubsystemHealth:
    name: str
    status: HealthStatus
    message: str
    checked_at: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "checked_at": self.checked_at,
        }


class HealthProbe:
    """Evaluates subsystem health based on metric thresholds."""

    # CPU queue_depth thresholds
    _CPU_DEGRADED = 50
    _CPU_CRITICAL = 200

    # RAM utilisation thresholds (percent)
    _RAM_DEGRADED = 80.0
    _RAM_CRITICAL = 95.0

    def check_cpu(self, cpu_metrics: dict) -> SubsystemHealth:
        depth = cpu_metrics.get("queue_depth", 0)
        now = utcnow()
        if depth >= self._CPU_CRITICAL:
            return SubsystemHealth(
                "cpu",
                HealthStatus.CRITICAL,
                f"CPU queue depth critical: {depth}",
                now,
            )
        if depth >= self._CPU_DEGRADED:
            return SubsystemHealth(
                "cpu",
                HealthStatus.DEGRADED,
                f"CPU queue depth elevated: {depth}",
                now,
            )
        return SubsystemHealth("cpu", HealthStatus.OK, f"CPU queue depth: {depth}", now)

    def check_ram(self, ram_usage: dict) -> SubsystemHealth:
        pct = ram_usage.get("utilisation_pct", 0.0)
        now = utcnow()
        if pct >= self._RAM_CRITICAL:
            return SubsystemHealth(
                "ram",
                HealthStatus.CRITICAL,
                f"RAM utilisation critical: {pct:.1f}%",
                now,
            )
        if pct >= self._RAM_DEGRADED:
            return SubsystemHealth(
                "ram",
                HealthStatus.DEGRADED,
                f"RAM utilisation elevated: {pct:.1f}%",
                now,
            )
        return SubsystemHealth("ram", HealthStatus.OK, f"RAM utilisation: {pct:.1f}%", now)

    def check_cloud(self, cloud_metrics: dict) -> SubsystemHealth:
        nodes_online = cloud_metrics.get("nodes_online", 0)
        now = utcnow()
        if nodes_online == 0:
            return SubsystemHealth(
                "cloud",
                HealthStatus.CRITICAL,
                "No cloud nodes online",
                now,
            )
        return SubsystemHealth(
            "cloud",
            HealthStatus.OK,
            f"{nodes_online} cloud node(s) online",
            now,
        )

    def check_all(self, metrics: dict) -> Dict[str, dict]:
        """Return a name → SubsystemHealth.to_dict() mapping."""
        results: Dict[str, dict] = {}
        cpu_metrics = metrics.get("cpu", {})
        ram_usage = metrics.get("ram", {})
        cloud_metrics = metrics.get("cloud", {})

        results["cpu"] = self.check_cpu(cpu_metrics).to_dict()
        results["ram"] = self.check_ram(ram_usage).to_dict()
        results["cloud"] = self.check_cloud(cloud_metrics).to_dict()
        return results
