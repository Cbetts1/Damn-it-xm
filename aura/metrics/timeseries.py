# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa TimeSeriesBuffer — rolling in-memory time-series store."""

from __future__ import annotations

import collections
import threading
from typing import Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.metrics.timeseries")


class TimeSeriesBuffer:
    """
    Thread-safe rolling buffer of ``{ts, value}`` data points per key.

    Backed by a ``collections.deque`` per key for O(1) append and pop.
    """

    def __init__(self, max_points: int = 120) -> None:
        self._max_points = max(1, max_points)
        self._data: Dict[str, collections.deque] = {}
        self._lock = threading.Lock()

    def record(
        self, key: str, value: float, timestamp: Optional[str] = None
    ) -> None:
        ts = timestamp or utcnow()
        point = {"ts": ts, "value": value}
        with self._lock:
            if key not in self._data:
                self._data[key] = collections.deque(maxlen=self._max_points)
            self._data[key].append(point)

    def get(self, key: str, last_n: int = 60) -> List[dict]:
        with self._lock:
            buf = self._data.get(key)
            if buf is None:
                return []
            points = list(buf)
        return points[-last_n:]

    def latest(self, key: str) -> Optional[float]:
        with self._lock:
            buf = self._data.get(key)
            if not buf:
                return None
            return buf[-1]["value"]

    def keys(self) -> List[str]:
        with self._lock:
            return list(self._data.keys())
