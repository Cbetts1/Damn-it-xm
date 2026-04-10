# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Filesystem Layer — FHS Mapper
====================================
Maps standard Filesystem Hierarchy Standard (FHS) paths to their
AURa virtual-path equivalents, providing a stable translation layer
between POSIX conventions and the AURa internal namespace.
"""

from __future__ import annotations

from typing import Dict

from aura.utils import get_logger

_logger = get_logger("aura.fs.fhs")

_DEFAULT_MAPPINGS: Dict[str, str] = {
    "/bin":     "aura:bin",
    "/etc":     "aura:config",
    "/var/log": "aura:logs",
    "/proc":    "aura:procfs",
    "/dev":     "aura:hardware",
    "/home":    "aura:userland",
    "/tmp":     "aura:temp",
    "/usr":     "aura:system",
    "/opt":     "aura:packages",
}


class FHSMapper:
    """
    Filesystem Hierarchy Standard path mapper.

    Translates well-known FHS paths (e.g. ``/etc``, ``/proc``) to their
    corresponding AURa virtual path identifiers (e.g. ``aura:config``).
    Mappings can be extended or overridden at runtime.
    """

    def __init__(self) -> None:
        self._mapping: Dict[str, str] = dict(_DEFAULT_MAPPINGS)
        _logger.info("FHSMapper initialised with %d default mappings", len(self._mapping))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, fhs_path: str) -> str:
        """
        Return the AURa virtual path for *fhs_path*.

        Looks up the exact path first, then tries progressively shorter
        parent prefixes so that sub-paths (e.g. ``/etc/aura``) resolve
        via their closest registered ancestor.  Falls back to returning
        *fhs_path* unchanged if no mapping is found.
        """
        # Exact match
        if fhs_path in self._mapping:
            return self._mapping[fhs_path]

        # Prefix match — find the longest registered prefix
        best_prefix: str = ""
        for registered in self._mapping:
            if fhs_path.startswith(registered.rstrip("/") + "/"):
                if len(registered) > len(best_prefix):
                    best_prefix = registered

        if best_prefix:
            remainder = fhs_path[len(best_prefix):]
            aura_base = self._mapping[best_prefix]
            resolved = f"{aura_base}{remainder}"
            _logger.debug("resolve: '%s' -> '%s' (prefix match)", fhs_path, resolved)
            return resolved

        _logger.warning("resolve: no mapping found for '%s', returning as-is", fhs_path)
        return fhs_path

    def list_mappings(self) -> Dict[str, str]:
        """Return a copy of all current FHS → AURa mappings."""
        return dict(self._mapping)

    def add_mapping(self, fhs_path: str, aura_path: str) -> None:
        """
        Add or update the mapping from *fhs_path* to *aura_path*.

        If a mapping already exists for *fhs_path* it is silently replaced.
        """
        previous = self._mapping.get(fhs_path)
        self._mapping[fhs_path] = aura_path
        if previous is None:
            _logger.info("add_mapping: '%s' -> '%s' added", fhs_path, aura_path)
        else:
            _logger.info(
                "add_mapping: '%s' updated '%s' -> '%s'",
                fhs_path, previous, aura_path,
            )
