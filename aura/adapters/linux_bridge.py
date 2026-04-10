# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Adapters — Linux platform bridge."""

from __future__ import annotations

import os
import platform
from typing import Dict, List, Optional

from aura.utils import get_logger
from aura.adapters.android_bridge import detect_capabilities


class LinuxBridge:
    """
    Linux-specific platform adapter for AURa.

    Provides system introspection helpers that work in both a real Linux
    environment and AURa's virtual OS environment.
    """

    def __init__(self, capabilities: Optional[Dict] = None) -> None:
        self._caps = capabilities or detect_capabilities()
        self._log = get_logger("aura.adapters.linux")
        self._log.debug("LinuxBridge initialised (platform=%s).", self._caps.get("platform"))

    def get_kernel_version(self) -> str:
        """Return the kernel version string, or a virtual fallback."""
        try:
            with open("/proc/version", "r", encoding="utf-8") as fh:
                return fh.readline().strip()
        except OSError:
            return "AURa-Linux-Virtual"

    def get_system_info(self) -> dict:
        """Return a dict of key system metrics using only the stdlib."""
        return {
            "platform": "linux",
            "kernel_version": self.get_kernel_version(),
            "cpu_count": os.cpu_count(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "node": platform.node(),
        }

    def list_processes(self) -> List[dict]:
        """Return a process list. In the virtual environment a mock list is used."""
        return [
            {"pid": 1, "name": "aura-init", "state": "running"},
            {"pid": 2, "name": "aura-kernel", "state": "running"},
            {"pid": 3, "name": "aura-shell", "state": "sleeping"},
        ]

    def get_network_interfaces(self) -> List[str]:
        """Return virtual network interface names."""
        return ["lo", "vnet0"]
