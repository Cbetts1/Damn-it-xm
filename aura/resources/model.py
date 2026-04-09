# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Resource Slot — a named, budgeted resource with allocation tracking."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from aura.utils import get_logger

_logger = get_logger("aura.resources.model")


@dataclass
class ResourceSlot:
    """A named resource with a total budget, reservations, and live allocations."""

    name: str
    total: float
    unit: str
    reserved: float = 0.0
    _allocated: float = field(default=0.0, compare=False, repr=False)
    _lock: threading.Lock = field(
        default_factory=threading.Lock, compare=False, repr=False
    )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def allocated(self) -> float:
        with self._lock:
            return self._allocated

    @property
    def available(self) -> float:
        with self._lock:
            return max(0.0, self.total - self._allocated - self.reserved)

    @property
    def utilisation_pct(self) -> float:
        if self.total <= 0:
            return 0.0
        with self._lock:
            return round((self._allocated / self.total) * 100.0, 2)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def allocate(self, amount: float) -> bool:
        """Attempt to allocate *amount* units. Returns False if over budget."""
        if amount < 0:
            raise ValueError(f"Cannot allocate negative amount: {amount}")
        with self._lock:
            if self._allocated + amount > self.total - self.reserved:
                _logger.debug(
                    "ResourceSlot(%s): allocation of %.2f denied — available=%.2f",
                    self.name,
                    amount,
                    self.total - self._allocated - self.reserved,
                )
                return False
            self._allocated += amount
            return True

    def release(self, amount: float) -> None:
        """Release *amount* units back to the pool."""
        if amount < 0:
            raise ValueError(f"Cannot release negative amount: {amount}")
        with self._lock:
            self._allocated = max(0.0, self._allocated - amount)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "name": self.name,
                "total": self.total,
                "unit": self.unit,
                "reserved": self.reserved,
                "allocated": round(self._allocated, 4),
                "available": round(max(0.0, self.total - self._allocated - self.reserved), 4),
                "utilisation_pct": self.utilisation_pct,
            }
