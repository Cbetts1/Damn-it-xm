# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Kernel — Service Manager
================================
Registers and supervises named OS-level services.  Each service has a
``start_fn`` and optional ``stop_fn``.  Services can be configured for
automatic restart on failure.
"""

from __future__ import annotations

import threading
from typing import Callable, Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.kernel.service_manager")

_VALID_STATES = ("active", "inactive", "failed")
_MAX_AUTO_RESTARTS = 3


class ServiceManager:
    """
    Registry and lifecycle controller for named AURA services.

    Services are registered once and may be started, stopped, and
    restarted.  All state mutations are protected by a ``threading.Lock``.
    """

    def __init__(self) -> None:
        self._services: Dict[str, dict] = {}
        self._lock = threading.Lock()
        _logger.info("ServiceManager initialised")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        start_fn: Callable,
        stop_fn: Optional[Callable] = None,
        auto_restart: bool = False,
    ) -> None:
        """
        Register a service.

        Parameters
        ----------
        name:
            Unique service name.
        start_fn:
            Zero-argument callable that starts the service.
        stop_fn:
            Optional zero-argument callable that stops the service.
        auto_restart:
            If ``True``, :meth:`start_service` will be called again
            after a failed start attempt.

        Raises
        ------
        ValueError
            If a service with *name* is already registered.
        """
        with self._lock:
            if name in self._services:
                raise ValueError(f"Service {name!r} is already registered")
            self._services[name] = {
                "name": name,
                "state": "inactive",
                "start_fn": start_fn,
                "stop_fn": stop_fn,
                "auto_restart": auto_restart,
                "restart_count": 0,
                "last_started": None,
            }
        _logger.info("Registered service: %s auto_restart=%s", name, auto_restart)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_service(self, name: str, _retry: int = 0) -> bool:
        """
        Start a registered service.

        Returns
        -------
        bool
            ``True`` on success, ``False`` if the service is unknown or
            the start function raises.
        """
        with self._lock:
            svc = self._services.get(name)
        if svc is None:
            _logger.warning("start_service: unknown service %s", name)
            return False

        try:
            svc["start_fn"]()
            with self._lock:
                svc["state"] = "active"
                svc["last_started"] = utcnow()
            _logger.info("Service started: %s", name)
            return True
        except Exception as exc:
            _logger.error("Service %s failed to start: %s", name, exc)
            with self._lock:
                svc["state"] = "failed"
            if svc["auto_restart"] and _retry < _MAX_AUTO_RESTARTS:
                _logger.info(
                    "Auto-restarting service: %s (attempt %d/%d)",
                    name, _retry + 1, _MAX_AUTO_RESTARTS,
                )
                with self._lock:
                    svc["restart_count"] += 1
                return self.start_service(name, _retry=_retry + 1)
            if svc["auto_restart"]:
                _logger.error(
                    "Service %s exceeded max auto-restart attempts (%d)",
                    name, _MAX_AUTO_RESTARTS,
                )
            return False

    def stop_service(self, name: str) -> bool:
        """
        Stop a running service.

        Returns
        -------
        bool
            ``True`` on success (or if no ``stop_fn`` was registered),
            ``False`` if the service is unknown or the stop function raises.
        """
        with self._lock:
            svc = self._services.get(name)
        if svc is None:
            _logger.warning("stop_service: unknown service %s", name)
            return False

        if svc["stop_fn"] is not None:
            try:
                svc["stop_fn"]()
            except Exception as exc:
                _logger.error("Service %s stop_fn raised: %s", name, exc)
                with self._lock:
                    svc["state"] = "failed"
                return False

        with self._lock:
            svc["state"] = "inactive"
        _logger.info("Service stopped: %s", name)
        return True

    def restart_service(self, name: str) -> bool:
        """Stop then start a service.  Returns ``True`` on overall success."""
        _logger.info("Restarting service: %s", name)
        self.stop_service(name)
        with self._lock:
            svc = self._services.get(name)
            if svc is not None:
                svc["restart_count"] += 1
        return self.start_service(name)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def status(self, name: str) -> Optional[dict]:
        """Return a copy of the service record, or ``None`` if not found."""
        with self._lock:
            svc = self._services.get(name)
        if svc is None:
            return None
        return {k: v for k, v in svc.items() if k not in ("start_fn", "stop_fn")}

    def list_services(self) -> List[dict]:
        """Return metadata for all registered services (callables excluded)."""
        with self._lock:
            return [
                {k: v for k, v in svc.items() if k not in ("start_fn", "stop_fn")}
                for svc in self._services.values()
            ]

    def metrics(self) -> Dict[str, int]:
        """Return service counts grouped by state."""
        counts: Dict[str, int] = {state: 0 for state in _VALID_STATES}
        with self._lock:
            for svc in self._services.values():
                state = svc.get("state", "inactive")
                counts[state] = counts.get(state, 0) + 1
        counts["total"] = sum(counts.values())
        return counts
