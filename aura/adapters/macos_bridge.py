# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Adapters — macOS platform bridge."""

from __future__ import annotations

import os
import platform
from typing import Dict, List, Optional

from aura.utils import get_logger
from aura.adapters.android_bridge import detect_capabilities


class MacOSBridge:
    """
    macOS-specific platform adapter for AURa.

    Provides system introspection helpers that work in both a real macOS
    environment and AURa's virtual OS environment.
    """

    def __init__(self, capabilities: Optional[Dict] = None) -> None:
        self._caps = capabilities or detect_capabilities()
        self._log = get_logger("aura.adapters.macos")
        self._log.debug("MacOSBridge initialised (platform=%s).", self._caps.get("platform"))

    def get_system_info(self) -> dict:
        """Return a dict of key system metrics using only the stdlib."""
        return {
            "platform": "darwin",
            "mac_version": platform.mac_ver()[0] or "AURa-macOS-Virtual",
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
        return ["lo0", "vnet0"]
