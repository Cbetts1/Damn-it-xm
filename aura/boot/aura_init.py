# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Init — PID-1 equivalent service manager
=============================================
aura-init is the first process to run after ROOT is online and HOME is
mounted.  It manages the lifecycle of all OS services.

Responsibilities:
  • Start and stop managed services in dependency order
  • Restart failed services (configurable retry policy)
  • Report service health to ROOT and the shell
  • Act as the reaping parent for all child services
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from aura.utils import get_logger, utcnow, EVENT_BUS

_logger = get_logger("aura.boot.init")


class ServiceState(str, Enum):
    STOPPED  = "stopped"
    STARTING = "starting"
    RUNNING  = "running"
    FAILED   = "failed"
    RESTARTING = "restarting"


@dataclass
class ServiceDescriptor:
    """Descriptor for a managed aura-init service."""

    name: str
    start_fn: Callable          # called to start the service
    stop_fn: Optional[Callable] = None   # called to stop the service
    restart_on_failure: bool = True
    max_restarts: int = 3
    restart_delay_s: float = 1.0

    # Runtime state (managed by AURAInit)
    state: ServiceState = ServiceState.STOPPED
    start_time: Optional[str] = None
    restart_count: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "start_time": self.start_time,
            "restart_count": self.restart_count,
            "last_error": self.last_error,
            "restart_on_failure": self.restart_on_failure,
            "max_restarts": self.max_restarts,
        }


class AURAInit:
    """
    aura-init — The AURA OS PID-1 equivalent.

    Manages all system services: starts them in registration order,
    monitors health, and stops them in reverse order on halt.
    """

    def __init__(self) -> None:
        self._services: Dict[str, ServiceDescriptor] = {}
        self._order: List[str] = []   # registration order
        self._lock = threading.RLock()
        self._running = False
        _logger.info("aura-init created")

    # ------------------------------------------------------------------
    # Service registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        start_fn: Callable,
        stop_fn: Optional[Callable] = None,
        restart_on_failure: bool = True,
        max_restarts: int = 3,
    ) -> None:
        """
        Register a service with aura-init.

        Services are started in registration order and stopped in
        reverse order.
        """
        with self._lock:
            if name in self._services:
                raise ValueError(f"Service {name!r} already registered")
            svc = ServiceDescriptor(
                name=name,
                start_fn=start_fn,
                stop_fn=stop_fn,
                restart_on_failure=restart_on_failure,
                max_restarts=max_restarts,
            )
            self._services[name] = svc
            self._order.append(name)
            _logger.debug("aura-init: registered service %r", name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_all(self) -> None:
        """Start all registered services in order."""
        _logger.info("aura-init: starting all services (%d total)", len(self._order))
        for name in self._order:
            self._start_service(name)
        self._running = True
        EVENT_BUS.publish("aura_init.started", {
            "service_count": len(self._order),
            "ts": utcnow(),
        })

    def stop_all(self) -> None:
        """Stop all services in reverse order."""
        _logger.info("aura-init: stopping all services…")
        for name in reversed(self._order):
            self._stop_service(name)
        self._running = False
        EVENT_BUS.publish("aura_init.stopped", {"ts": utcnow()})

    def restart_service(self, name: str) -> bool:
        """Restart a single service by name.  Returns True on success."""
        with self._lock:
            if name not in self._services:
                return False
        self._stop_service(name)
        time.sleep(0.1)
        self._start_service(name)
        return True

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def list_services(self) -> List[dict]:
        with self._lock:
            return [svc.to_dict() for svc in self._services.values()]

    def get_service(self, name: str) -> Optional[dict]:
        with self._lock:
            svc = self._services.get(name)
            return svc.to_dict() if svc else None

    def status(self) -> dict:
        with self._lock:
            running = sum(
                1 for s in self._services.values()
                if s.state == ServiceState.RUNNING
            )
            failed = sum(
                1 for s in self._services.values()
                if s.state == ServiceState.FAILED
            )
            return {
                "running": self._running,
                "total_services": len(self._services),
                "running_services": running,
                "failed_services": failed,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _start_service(self, name: str) -> None:
        with self._lock:
            svc = self._services[name]
            svc.state = ServiceState.STARTING
        try:
            svc.start_fn()
            with self._lock:
                svc.state = ServiceState.RUNNING
                svc.start_time = utcnow()
            _logger.info("aura-init: service %r started", name)
            EVENT_BUS.publish("service.started", {"name": name})
        except Exception as exc:
            with self._lock:
                svc.state = ServiceState.FAILED
                svc.last_error = str(exc)
            _logger.error("aura-init: service %r failed to start: %s", name, exc)
            EVENT_BUS.publish("service.failed", {"name": name, "error": str(exc)})

            # Restart logic — runs inline in the calling thread.
            # If many services fail simultaneously this will serialise their
            # restart delays.  For production use, move restart scheduling to
            # a background ThreadPoolExecutor.
            if svc.restart_on_failure and svc.restart_count < svc.max_restarts:
                svc.restart_count += 1
                _logger.info(
                    "aura-init: restarting %r (attempt %d/%d) in %.1fs",
                    name, svc.restart_count, svc.max_restarts, svc.restart_delay_s,
                )
                time.sleep(svc.restart_delay_s)
                svc.state = ServiceState.RESTARTING
                self._start_service(name)

    def _stop_service(self, name: str) -> None:
        with self._lock:
            svc = self._services.get(name)
            if svc is None or svc.state == ServiceState.STOPPED:
                return
            stop_fn = svc.stop_fn
        try:
            if stop_fn:
                stop_fn()
            with self._lock:
                svc.state = ServiceState.STOPPED
            _logger.info("aura-init: service %r stopped", name)
            EVENT_BUS.publish("service.stopped", {"name": name})
        except Exception as exc:
            _logger.warning("aura-init: service %r stop error: %s", name, exc)
            with self._lock:
                svc.state = ServiceState.STOPPED  # force-stopped
