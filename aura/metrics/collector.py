# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa MetricsCollector — background daemon that samples all subsystems."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

from aura.metrics.timeseries import TimeSeriesBuffer
from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.os_core.ai_os import AIOS

_logger = get_logger("aura.metrics.collector")


class MetricsCollector:
    """
    Runs a background daemon thread that calls ``collect_now()`` every
    *interval_seconds* seconds and feeds results into a ``TimeSeriesBuffer``.
    """

    def __init__(
        self,
        aios_ref: "AIOS",
        timeseries: TimeSeriesBuffer,
        interval_seconds: float = 5.0,
    ) -> None:
        self._aios = aios_ref
        self._ts = timeseries
        self._interval = max(0.1, interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="aura-metrics-collector",
            daemon=True,
        )
        self._thread.start()
        _logger.info("MetricsCollector started (interval=%.1fs)", self._interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=max(self._interval + 1, 5))
        _logger.info("MetricsCollector stopped")

    def collect_now(self) -> dict:
        """Pull a snapshot from all available subsystems and record time-series."""
        snapshot: dict[str, Any] = {}

        try:
            cpu = self._aios._cpu
            if cpu is not None:
                m = cpu.metrics()
                snapshot["cpu"] = m
                self._ts.record("cpu.queue_depth", float(m.get("queue_depth", 0)))
                self._ts.record("cpu.tasks_completed", float(m.get("tasks_completed", 0)))
                self._ts.record("cpu.workers_active", float(m.get("workers_active", 0)))
        except Exception as exc:
            _logger.debug("MetricsCollector: cpu error: %s", exc)

        try:
            cloud = self._aios._cloud
            if cloud is not None:
                cm = cloud.metrics()
                snapshot["cloud"] = cm
                self._ts.record("cloud.cpu_utilisation_pct", float(cm.get("cpu_utilisation_pct", 0)))
                self._ts.record("cloud.memory_utilisation_pct", float(cm.get("memory_utilisation_pct", 0)))
        except Exception as exc:
            _logger.debug("MetricsCollector: cloud error: %s", exc)

        try:
            ram = self._aios._ram
            if ram is not None:
                ru = ram.usage()
                snapshot["ram"] = ru
                self._ts.record("ram.utilisation_pct", float(ru.get("utilisation_pct", 0)))
        except Exception as exc:
            _logger.debug("MetricsCollector: ram error: %s", exc)

        return snapshot

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.collect_now()
            except Exception as exc:
                _logger.debug("MetricsCollector loop error: %s", exc)
            self._stop_event.wait(timeout=self._interval)
