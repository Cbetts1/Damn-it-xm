# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa /dev/vram — Virtual RAM Device
=====================================
Tracks virtual memory allocations, pressure, and limits for all
processes and subsystems running inside AURA.

All allocations must fit within the configured ``total_mb`` cap.  When
the cap is approached, the device emits a ``vram.pressure`` event on
the EventBus.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow, EVENT_BUS

_logger = get_logger("aura.hardware.vram")

DEV_PATH = "/dev/vram"

_PRESSURE_THRESHOLD_PCT = 80.0   # fire event at 80 % utilisation
_CRITICAL_THRESHOLD_PCT = 95.0   # fire critical event at 95 %


@dataclass
class MemoryAllocation:
    """A single virtual memory allocation."""
    alloc_id: str
    owner: str          # the subsystem/process that owns this block
    size_mb: float
    label: str          # human-readable label
    allocated_at: str

    def to_dict(self) -> dict:
        return {
            "alloc_id": self.alloc_id,
            "owner": self.owner,
            "size_mb": self.size_mb,
            "label": self.label,
            "allocated_at": self.allocated_at,
        }


class VRAMDevice:
    """
    /dev/vram — Virtual RAM device.

    Parameters
    ----------
    total_mb:
        Total virtual RAM capacity in megabytes.
    """

    def __init__(self, total_mb: float = 32_768.0) -> None:
        self._total_mb = total_mb
        self._allocations: Dict[str, MemoryAllocation] = {}
        self._lock = threading.RLock()
        _logger.info("/dev/vram: %g MB total virtual RAM", total_mb)

    @property
    def path(self) -> str:
        return DEV_PATH

    # ------------------------------------------------------------------
    # Allocation API
    # ------------------------------------------------------------------

    def allocate(self, owner: str, size_mb: float, label: str = "") -> str:
        """
        Allocate *size_mb* megabytes for *owner*.

        Returns
        -------
        str
            Allocation ID.

        Raises
        ------
        MemoryError
            If there is insufficient virtual RAM.
        """
        with self._lock:
            available = self._total_mb - self._used_mb()
            if size_mb > available:
                raise MemoryError(
                    f"/dev/vram: insufficient memory "
                    f"(requested={size_mb:.1f} MB  available={available:.1f} MB)"
                )
            alloc_id = generate_id("vram")
            self._allocations[alloc_id] = MemoryAllocation(
                alloc_id=alloc_id,
                owner=owner,
                size_mb=size_mb,
                label=label or owner,
                allocated_at=utcnow(),
            )
            self._check_pressure()
            _logger.debug(
                "/dev/vram: allocated %.1f MB for %s (id=%s)",
                size_mb, owner, alloc_id,
            )
            return alloc_id

    def free(self, alloc_id: str) -> bool:
        """Free an allocation.  Returns True if freed."""
        with self._lock:
            if alloc_id not in self._allocations:
                return False
            del self._allocations[alloc_id]
            _logger.debug("/dev/vram: freed allocation %s", alloc_id)
            return True

    def free_owner(self, owner: str) -> int:
        """Free all allocations for *owner*.  Returns count freed."""
        with self._lock:
            ids = [a.alloc_id for a in self._allocations.values()
                   if a.owner == owner]
            for aid in ids:
                del self._allocations[aid]
            if ids:
                _logger.debug("/dev/vram: freed %d allocations for %s", len(ids), owner)
            return len(ids)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics(self) -> dict:
        with self._lock:
            used = self._used_mb()
            pct = (used / self._total_mb * 100.0) if self._total_mb > 0 else 0.0
            return {
                "device": DEV_PATH,
                "total_mb": self._total_mb,
                "used_mb": round(used, 2),
                "free_mb": round(self._total_mb - used, 2),
                "utilisation_pct": round(pct, 2),
                "allocation_count": len(self._allocations),
            }

    def list_allocations(self) -> List[dict]:
        with self._lock:
            return [a.to_dict() for a in self._allocations.values()]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _used_mb(self) -> float:
        return sum(a.size_mb for a in self._allocations.values())

    def _check_pressure(self) -> None:
        pct = self._used_mb() / self._total_mb * 100.0
        if pct >= _CRITICAL_THRESHOLD_PCT:
            EVENT_BUS.publish("vram.critical", {"utilisation_pct": pct})
            _logger.warning("/dev/vram: CRITICAL pressure %.1f%%", pct)
        elif pct >= _PRESSURE_THRESHOLD_PCT:
            EVENT_BUS.publish("vram.pressure", {"utilisation_pct": pct})
            _logger.warning("/dev/vram: memory pressure %.1f%%", pct)
