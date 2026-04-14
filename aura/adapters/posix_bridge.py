# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Adapters — shared POSIX base class for Linux and macOS bridges."""

from __future__ import annotations

import os
import platform
from typing import Dict, List, Optional

from aura.utils import get_logger
from aura.adapters.android_bridge import detect_capabilities


class PosixBridge:
    """
    Shared base class for POSIX platform adapters (Linux, macOS).

    Provides default implementations of ``list_processes`` and
    ``get_network_interfaces`` that return a virtual mock process list and
    interface names.  Subclasses override ``get_system_info`` and, where
    needed, ``get_network_interfaces`` to return platform-specific values.
    """

    _PLATFORM_NAME: str = "posix"

    def __init__(self, capabilities: Optional[Dict] = None) -> None:
        self._caps = capabilities or detect_capabilities()
        self._log = get_logger(f"aura.adapters.{self._PLATFORM_NAME}")
        self._log.debug(
            "%s initialised (platform=%s).",
            self.__class__.__name__,
            self._caps.get("platform"),
        )

    def get_system_info(self) -> dict:  # pragma: no cover
        """Return a dict of key system metrics.  Subclasses should override."""
        return {
            "platform": self._PLATFORM_NAME,
            "cpu_count": os.cpu_count(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "node": platform.node(),
        }

    def list_processes(self) -> List[dict]:
        """Return a virtual process list (mock).  Shared across POSIX platforms."""
        return [
            {"pid": 1, "name": "aura-init", "state": "running"},
            {"pid": 2, "name": "aura-kernel", "state": "running"},
            {"pid": 3, "name": "aura-shell", "state": "sleeping"},
        ]

    def get_network_interfaces(self) -> List[str]:
        """Return virtual network interface names.  Subclasses may override."""
        return ["lo", "vnet0"]
