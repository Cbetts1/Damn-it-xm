# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Package Manager — package installer."""

from __future__ import annotations

import threading
from typing import Dict, List

from aura.utils import get_logger, utcnow
from aura.pkg.metadata import PackageStatus
from aura.pkg.registry import PackageRegistry


class PackageInstaller:
    """Thread-safe installer that tracks installed packages against a registry."""

    def __init__(self, registry: PackageRegistry) -> None:
        self._registry = registry
        self._installed: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._log = get_logger("aura.pkg.installer")

    def install(self, name: str) -> dict:
        meta = self._registry.get(name)
        if meta is None:
            self._log.warning("Install failed — package not in registry: %s", name)
            return {"success": False, "message": f"Package '{name}' not found in registry."}
        with self._lock:
            if name in self._installed:
                self._log.info("Package already installed: %s", name)
                return {"success": False, "message": f"Package '{name}' is already installed."}
            self._installed[name] = {
                "name": name,
                "version": meta.version,
                "installed_at": utcnow(),
                "status": PackageStatus.INSTALLED.value,
            }
        self._log.info("Installed package: %s v%s", name, meta.version)
        return {"success": True, "message": f"Package '{name}' v{meta.version} installed successfully."}

    def uninstall(self, name: str) -> dict:
        with self._lock:
            if name not in self._installed:
                self._log.warning("Uninstall failed — package not installed: %s", name)
                return {"success": False, "message": f"Package '{name}' is not installed."}
            del self._installed[name]
        self._log.info("Uninstalled package: %s", name)
        return {"success": True, "message": f"Package '{name}' uninstalled successfully."}

    def upgrade(self, name: str) -> dict:
        meta = self._registry.get(name)
        if meta is None:
            self._log.warning("Upgrade failed — package not in registry: %s", name)
            return {"success": False, "message": f"Package '{name}' not found in registry."}
        with self._lock:
            self._installed[name] = {
                "name": name,
                "version": meta.version,
                "installed_at": utcnow(),
                "status": PackageStatus.INSTALLED.value,
            }
        self._log.info("Upgraded package: %s v%s", name, meta.version)
        return {"success": True, "message": f"Package '{name}' upgraded to v{meta.version}."}

    def is_installed(self, name: str) -> bool:
        with self._lock:
            return name in self._installed

    def list_installed(self) -> List[dict]:
        with self._lock:
            return list(self._installed.values())

    def get_status(self, name: str) -> str:
        with self._lock:
            if name in self._installed:
                return self._installed[name]["status"]
        if self._registry.get(name) is not None:
            return PackageStatus.AVAILABLE.value
        return PackageStatus.BROKEN.value
