# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Package Manager — package registry."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from aura.utils import get_logger, utcnow
from aura.pkg.metadata import PackageMetadata

_BUILTIN_PACKAGES = [
    PackageMetadata(
        name="aura-core",
        version="1.0.0",
        description="AURa core runtime and kernel primitives.",
        author="AURa Project",
        dependencies=[],
        tags=["core", "system"],
        license="MIT",
        size_bytes=204800,
        checksum="",
        created_at="2024-01-01T00:00:00+00:00",
        homepage="https://github.com/Cbetts1/Damn-it-xm",
    ),
    PackageMetadata(
        name="aura-shell",
        version="1.0.0",
        description="AURa interactive shell and command processor.",
        author="AURa Project",
        dependencies=["aura-core"],
        tags=["shell", "cli"],
        license="MIT",
        size_bytes=102400,
        checksum="",
        created_at="2024-01-01T00:00:00+00:00",
        homepage="https://github.com/Cbetts1/Damn-it-xm",
    ),
    PackageMetadata(
        name="aura-net",
        version="1.0.0",
        description="AURa virtual network stack and adapters.",
        author="AURa Project",
        dependencies=["aura-core"],
        tags=["network", "net"],
        license="MIT",
        size_bytes=81920,
        checksum="",
        created_at="2024-01-01T00:00:00+00:00",
        homepage="https://github.com/Cbetts1/Damn-it-xm",
    ),
]


class PackageRegistry:
    """Thread-safe registry of all packages known to the AURa package manager."""

    def __init__(self) -> None:
        self._packages: Dict[str, PackageMetadata] = {}
        self._lock = threading.Lock()
        self._log = get_logger("aura.pkg.registry")
        for pkg in _BUILTIN_PACKAGES:
            self._packages[pkg.name] = pkg
        self._log.debug("Registry initialised with %d built-in packages.", len(self._packages))

    def register(self, meta: PackageMetadata) -> None:
        with self._lock:
            self._packages[meta.name] = meta
        self._log.info("Registered package: %s v%s", meta.name, meta.version)

    def get(self, name: str) -> Optional[PackageMetadata]:
        with self._lock:
            return self._packages.get(name)

    def search(self, query: str) -> List[PackageMetadata]:
        q = query.lower()
        with self._lock:
            results = [
                pkg for pkg in self._packages.values()
                if q in pkg.name.lower()
                or q in pkg.description.lower()
                or any(q in tag.lower() for tag in pkg.tags)
            ]
        self._log.debug("Search %r returned %d result(s).", query, len(results))
        return results

    def list_all(self) -> List[PackageMetadata]:
        with self._lock:
            return list(self._packages.values())

    def unregister(self, name: str) -> bool:
        with self._lock:
            if name in self._packages:
                del self._packages[name]
                self._log.info("Unregistered package: %s", name)
                return True
        self._log.warning("Unregister failed — package not found: %s", name)
        return False

    def count(self) -> int:
        with self._lock:
            return len(self._packages)
