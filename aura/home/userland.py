# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa HOME — Userland Layer
===========================
HOME is the Termux-class userland that sits above ROOT.

It provides:
  • An isolated filesystem overlay (:class:`~aura.home.filesystem.HomeFilesystem`)
  • Process-level isolation (each process gets a scoped environment)
  • Restricted access to /dev/* through ROOT-gated interfaces
  • Package manager concept (register/list/remove packages)
  • Per-user environment management

HOME is mounted by ROOT after the boot chain confirms ROOT is online.
HOME processes may not escalate to ROOT privileges directly.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aura.config import HOMEConfig
from aura.home.filesystem import HomeFilesystem
from aura.utils import get_logger, generate_id, utcnow, EVENT_BUS

_logger = get_logger("aura.home")


@dataclass
class HomePackage:
    """A registered HOME userland package."""
    package_id: str
    name: str
    version: str
    description: str
    installed_at: str
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "installed_at": self.installed_at,
            "active": self.active,
        }


@dataclass
class HomeProcess:
    """A tracked process running inside HOME."""
    pid: str
    name: str
    owner: str
    started_at: str
    state: str = "running"

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "owner": self.owner,
            "started_at": self.started_at,
            "state": self.state,
        }


class HOMELayer:
    """
    HOME userland layer.

    Parameters
    ----------
    config:
        HOMEConfig from the system configuration.
    """

    def __init__(self, config: HOMEConfig) -> None:
        self._config = config
        self._fs = HomeFilesystem(config.home_dir)
        self._packages: Dict[str, HomePackage] = {}
        self._processes: Dict[str, HomeProcess] = {}
        self._lock = threading.RLock()
        self._running = False
        _logger.info("HOME layer created (home_dir=%s)", config.home_dir)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def filesystem(self) -> HomeFilesystem:
        return self._fs

    @property
    def running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Mount HOME filesystem and initialise userland environment."""
        if self._running:
            return
        _logger.info("HOME: mounting filesystem…")
        self._fs.mount()
        self._write_os_release()
        self._install_default_packages()
        self._running = True
        EVENT_BUS.publish("home.started", {"home_dir": self._config.home_dir})
        _logger.info("HOME: userland online")

    def stop(self) -> None:
        """Unmount HOME and clean up."""
        if not self._running:
            return
        _logger.info("HOME: stopping…")
        # Mark all processes as stopped
        with self._lock:
            for proc in self._processes.values():
                proc.state = "stopped"
        self._fs.unmount()
        self._running = False
        EVENT_BUS.publish("home.stopped", {})
        _logger.info("HOME: userland offline")

    # ------------------------------------------------------------------
    # Package management
    # ------------------------------------------------------------------

    def install_package(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
    ) -> HomePackage:
        """Register a package as installed in HOME."""
        with self._lock:
            pkg = HomePackage(
                package_id=generate_id("pkg"),
                name=name,
                version=version,
                description=description,
                installed_at=utcnow(),
            )
            self._packages[name] = pkg
            _logger.info("HOME: installed package %s %s", name, version)
            return pkg

    def remove_package(self, name: str) -> bool:
        with self._lock:
            if name in self._packages:
                del self._packages[name]
                _logger.info("HOME: removed package %s", name)
                return True
            return False

    def list_packages(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self._packages.values()]

    # ------------------------------------------------------------------
    # Process tracking
    # ------------------------------------------------------------------

    def spawn(self, name: str, owner: str = "aura") -> HomeProcess:
        """Track a new HOME process."""
        with self._lock:
            proc = HomeProcess(
                pid=generate_id("proc"),
                name=name,
                owner=owner,
                started_at=utcnow(),
            )
            self._processes[proc.pid] = proc
            _logger.debug("HOME: process %s spawned (owner=%s)", name, owner)
            return proc

    def kill(self, pid: str) -> bool:
        with self._lock:
            if pid in self._processes:
                self._processes[pid].state = "stopped"
                return True
            return False

    def list_processes(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self._processes.values()
                    if p.state == "running"]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "home_dir": self._config.home_dir,
                "packages": len(self._packages),
                "processes": len([p for p in self._processes.values()
                                  if p.state == "running"]),
                "fs": self._fs.metrics(),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_os_release(self) -> None:
        """Write /etc/os-release equivalent into HOME/etc."""
        content = (
            'NAME="AURa OS"\n'
            'VERSION="1.2.0"\n'
            'ID=aura\n'
            'ID_LIKE=linux\n'
            'HOME_URL="https://github.com/Cbetts1/Damn-it-xm"\n'
            'PRETTY_NAME="AURa OS 1.2.0 (Autonomous Universal Resource Architecture)"\n'
        )
        try:
            self._fs.write(content, "etc", "os-release")
        except Exception as exc:
            _logger.warning("HOME: could not write os-release: %s", exc)

    def _install_default_packages(self) -> None:
        """Pre-install the default HOME package set."""
        defaults = [
            ("aura-shell",    "1.2.0", "AURa interactive shell"),
            ("aura-ai",       "1.2.0", "AURa AI engine"),
            ("aura-utils",    "1.2.0", "AURa utility toolkit"),
            ("aura-net",      "1.2.0", "AURa network tools"),
            ("aura-build",    "1.2.0", "AURa build pipeline"),
            ("aura-crypto",   "1.2.0", "AURa cryptographic identity tools"),
        ]
        for name, version, desc in defaults:
            if name not in self._packages:
                self.install_package(name, version, desc)
