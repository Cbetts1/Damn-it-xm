# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Kernel — Cron Service
============================
Lightweight periodic job scheduler.  Jobs are registered with a name,
callable, and interval; a background daemon thread fires each job when
its ``next_run`` timestamp is due.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.kernel.cron")

_TICK = 0.1  # seconds between scheduler sweeps


class CronService:
    """
    Periodic job scheduler backed by a single daemon thread.

    Jobs are executed in the scheduler thread sequentially; for
    long-running work, the registered function should itself spawn a
    thread or delegate to :class:`~aura.kernel.process_manager.ProcessManager`.
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        _logger.info("CronService initialised")

    # ------------------------------------------------------------------
    # Job registration
    # ------------------------------------------------------------------

    def add_job(self, name: str, fn: Callable, interval_seconds: float) -> str:
        """
        Register a new periodic job.

        Parameters
        ----------
        name:
            Human-readable job name.
        fn:
            Zero-argument callable to invoke on each tick.
        interval_seconds:
            How often (in seconds) the job should run.

        Returns
        -------
        str
            The assigned job ID.
        """
        job_id = generate_id("cron")
        now = time.monotonic()
        entry: dict = {
            "job_id": job_id,
            "name": name,
            "fn": fn,
            "interval_seconds": interval_seconds,
            "last_run": None,
            "next_run": now + interval_seconds,
            "enabled": True,
            "run_count": 0,
        }
        with self._lock:
            self._jobs[job_id] = entry
        _logger.info("CronService: added job job_id=%s name=%s interval=%ss",
                     job_id, name, interval_seconds)
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID.  Returns ``True`` if it existed."""
        with self._lock:
            existed = job_id in self._jobs
            self._jobs.pop(job_id, None)
        if existed:
            _logger.info("CronService: removed job_id=%s", job_id)
        return existed

    def enable_job(self, job_id: str) -> bool:
        """Enable a disabled job.  Returns ``False`` if not found."""
        return self._set_enabled(job_id, True)

    def disable_job(self, job_id: str) -> bool:
        """Disable a job without removing it.  Returns ``False`` if not found."""
        return self._set_enabled(job_id, False)

    # ------------------------------------------------------------------
    # Scheduler lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler thread."""
        if self._running:
            _logger.warning("CronService already running")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            name="cron-scheduler",
            daemon=True,
        )
        self._thread.start()
        _logger.info("CronService started")

    def stop(self) -> None:
        """Stop the background scheduler thread."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=_TICK * 2)
            self._thread = None
        _logger.info("CronService stopped")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_jobs(self) -> List[dict]:
        """Return job metadata (the callable is excluded)."""
        with self._lock:
            return [
                {k: v for k, v in job.items() if k != "fn"}
                for job in self._jobs.values()
            ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_enabled(self, job_id: str, enabled: bool) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            job["enabled"] = enabled
        _logger.debug("CronService: job_id=%s enabled=%s", job_id, enabled)
        return True

    def _loop(self) -> None:
        """Scheduler sweep: fire any jobs whose next_run is in the past."""
        while self._running:
            now = time.monotonic()
            with self._lock:
                due = [
                    job for job in self._jobs.values()
                    if job["enabled"] and job["next_run"] <= now
                ]

            for job in due:
                self._fire(job)

            time.sleep(_TICK)

    def _fire(self, job: dict) -> None:
        job_id = job["job_id"]
        try:
            job["fn"]()
        except Exception as exc:
            _logger.error("CronService: job_id=%s raised: %s", job_id, exc)
        finally:
            now = time.monotonic()
            with self._lock:
                live = self._jobs.get(job_id)
                if live is not None:
                    live["last_run"] = now
                    live["next_run"] = now + live["interval_seconds"]
                    live["run_count"] += 1
        _logger.debug("CronService: fired job_id=%s run_count=%d",
                      job_id, job.get("run_count", 0))
