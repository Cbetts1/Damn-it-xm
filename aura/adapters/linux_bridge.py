# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Adapters — Linux platform bridge."""

from __future__ import annotations

import os
import platform
from typing import Dict, List, Optional

from aura.adapters.posix_bridge import PosixBridge


class LinuxBridge(PosixBridge):
    """
    Linux-specific platform adapter for AURa.

    Provides system introspection helpers that work in both a real Linux
    environment and AURa's virtual OS environment.
    """

    _PLATFORM_NAME = "linux"

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

