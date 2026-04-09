# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa ToolRegistry — discovers and tracks external tools available on PATH."""

from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.orchestration.tool_registry")

_COMMON_TOOLS = [
    "python", "python3", "git", "curl", "wget", "pip", "pip3",
    "bash", "sh", "node", "npm", "java", "gcc", "make", "tar",
]


@dataclass
class ToolEntry:
    name: str
    path: str
    version: str
    capabilities: List[str]
    registered_at: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "version": self.version,
            "capabilities": self.capabilities,
            "registered_at": self.registered_at,
        }


class ToolRegistry:
    """Registry of external tools available for orchestrated workloads."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolEntry] = {}
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        path: str,
        version: str = "unknown",
        capabilities: Optional[List[str]] = None,
    ) -> ToolEntry:
        entry = ToolEntry(
            name=name,
            path=path,
            version=version,
            capabilities=capabilities or [],
            registered_at=utcnow(),
        )
        with self._lock:
            self._tools[name] = entry
        _logger.debug("Tool registered: %s → %s", name, path)
        return entry

    def get(self, name: str) -> Optional[ToolEntry]:
        with self._lock:
            return self._tools.get(name)

    def list_tools(self) -> List[dict]:
        with self._lock:
            return [e.to_dict() for e in self._tools.values()]

    def unregister(self, name: str) -> bool:
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                return True
        return False

    def discover(self) -> List[str]:
        """Scan PATH for common tools and auto-register them. Returns list of found names."""
        found = []
        for tool in _COMMON_TOOLS:
            path = shutil.which(tool)
            if path:
                with self._lock:
                    if tool not in self._tools:
                        self._tools[tool] = ToolEntry(
                            name=tool,
                            path=path,
                            version="auto-discovered",
                            capabilities=[],
                            registered_at=utcnow(),
                        )
                found.append(tool)
        _logger.info("Tool discovery found %d tools: %s", len(found), found)
        return found
