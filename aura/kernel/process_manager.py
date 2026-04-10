# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Kernel — Process Manager
==============================
Manages the lifecycle of lightweight virtual processes, each backed by a
daemon thread.  Processes are tracked in-memory; state transitions are
thread-safe.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.kernel.process_manager")

_VALID_STATES = ("running", "stopped", "zombie")


class ProcessManager:
    """
    Registry and supervisor for virtual processes.

    Each spawned process runs its callable in a daemon thread.  The
    manager records runtime metadata and exposes controls for listing
    and terminating processes.
    """

    def __init__(self) -> None:
        self._processes: Dict[str, dict] = {}
        self._lock = threading.Lock()
        _logger.info("ProcessManager initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def spawn(
        self,
        name: str,
        fn: Callable,
        user_id: Optional[str] = None,
        ram_mb: float = 0.0,
    ) -> str:
        """
        Create a process entry and run *fn* in a daemon thread.

        Parameters
        ----------
        name:
            Human-readable process name.
        fn:
            Zero-argument callable to execute.
        user_id:
            Optional owning user identifier.
        ram_mb:
            Declared RAM allocation in megabytes (informational).

        Returns
        -------
        str
            The newly assigned process ID.
        """
        pid = generate_id("proc")
        entry: dict = {
            "pid": pid,
            "name": name,
            "state": "running",
            "user_id": user_id,
            "started_at": utcnow(),
            "cpu_ms": 0.0,
            "ram_mb": ram_mb,
        }
        with self._lock:
            self._processes[pid] = entry

        thread = threading.Thread(
            target=self._run,
            args=(pid, fn),
            name=f"proc-{pid}",
            daemon=True,
        )
        thread.start()
        _logger.info("Spawned process pid=%s name=%s user_id=%s", pid, name, user_id)
        return pid

    def kill(self, pid: str) -> bool:
        """
        Mark a process as stopped.

        The underlying thread is not forcefully terminated (Python does not
        support that); the state is set to ``"stopped"`` so that callers
        know the process should be considered inactive.

        Returns
        -------
        bool
            ``True`` if the process existed, ``False`` otherwise.
        """
        with self._lock:
            proc = self._processes.get(pid)
            if proc is None:
                _logger.warning("kill: pid=%s not found", pid)
                return False
            proc["state"] = "stopped"
        _logger.info("Killed process pid=%s", pid)
        return True

    def list_processes(self, user_id: Optional[str] = None) -> List[dict]:
        """Return all process records, optionally filtered by *user_id*."""
        with self._lock:
            procs = list(self._processes.values())
        if user_id is not None:
            procs = [p for p in procs if p["user_id"] == user_id]
        return [dict(p) for p in procs]

    def get_process(self, pid: str) -> Optional[dict]:
        """Return a copy of the process record for *pid*, or ``None``."""
        with self._lock:
            proc = self._processes.get(pid)
        return dict(proc) if proc else None

    def metrics(self) -> dict:
        """Return process counts grouped by state."""
        counts: dict = {state: 0 for state in _VALID_STATES}
        with self._lock:
            for proc in self._processes.values():
                state = proc.get("state", "zombie")
                counts[state] = counts.get(state, 0) + 1
        counts["total"] = sum(counts.values())
        return counts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self, pid: str, fn: Callable) -> None:
        """Thread target: execute *fn* and update process state on exit."""
        import time

        start = time.monotonic()
        try:
            fn()
        except Exception as exc:
            _logger.error("Process pid=%s raised: %s", pid, exc)
            self._set_state(pid, "zombie")
        else:
            self._set_state(pid, "stopped")
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            with self._lock:
                proc = self._processes.get(pid)
                if proc is not None:
                    proc["cpu_ms"] = elapsed_ms

    def _set_state(self, pid: str, state: str) -> None:
        with self._lock:
            proc = self._processes.get(pid)
            if proc is not None and proc["state"] == "running":
                proc["state"] = state
        _logger.debug("Process pid=%s state -> %s", pid, state)
