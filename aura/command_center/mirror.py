# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Mirror Service
===================
Tracks mirror endpoints for content distribution and provides failover logic.
Thread-safe.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.command_center.mirror")

_VALID_TYPES = {"primary", "secondary", "backup"}
_VALID_STATUSES = {"online", "offline", "syncing"}


class MirrorService:
    """Registry and coordinator for AURa mirror endpoints."""

    def __init__(self) -> None:
        self._mirrors: Dict[str, dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_mirror(
        self,
        name: str,
        url: str,
        mirror_type: str = "secondary",
        priority: int = 0,
    ) -> str:
        """Register a new mirror and return its mirror_id."""
        mirror_id = generate_id("mirror")
        record = {
            "mirror_id": mirror_id,
            "url": url,
            "name": name,
            "type": mirror_type if mirror_type in _VALID_TYPES else "secondary",
            "status": "online",
            "last_sync": None,
            "sync_count": 0,
            "priority": priority,
        }
        with self._lock:
            self._mirrors[mirror_id] = record
        _logger.info("Added mirror '%s' (id=%s, type=%s, url=%s).", name, mirror_id, mirror_type, url)
        return mirror_id

    def remove_mirror(self, mirror_id: str) -> bool:
        """Remove a mirror by id.  Returns False if not found."""
        with self._lock:
            if mirror_id not in self._mirrors:
                return False
            name = self._mirrors.pop(mirror_id)["name"]
        _logger.info("Removed mirror '%s' (id=%s).", name, mirror_id)
        return True

    def get_mirror(self, mirror_id: str) -> Optional[dict]:
        """Return a mirror record by id, or None."""
        with self._lock:
            record = self._mirrors.get(mirror_id)
            return dict(record) if record else None

    def list_mirrors(self, status: Optional[str] = None) -> List[dict]:
        """Return all mirror records, optionally filtered by status."""
        with self._lock:
            records = list(self._mirrors.values())
        if status is not None:
            records = [r for r in records if r["status"] == status]
        return [dict(r) for r in records]

    def set_status(self, mirror_id: str, status: str) -> bool:
        """Update mirror status.  Returns False if mirror_id unknown."""
        if status not in _VALID_STATUSES:
            _logger.warning("set_status: invalid status '%s'.", status)
            return False
        with self._lock:
            if mirror_id not in self._mirrors:
                return False
            self._mirrors[mirror_id]["status"] = status
        _logger.debug("Mirror %s status -> '%s'.", mirror_id, status)
        return True

    def mark_synced(self, mirror_id: str) -> bool:
        """Record a successful sync event.  Returns False if mirror_id unknown."""
        with self._lock:
            if mirror_id not in self._mirrors:
                return False
            self._mirrors[mirror_id]["last_sync"] = utcnow()
            self._mirrors[mirror_id]["sync_count"] += 1
        _logger.debug("Mirror %s synced (count=%d).", mirror_id, self._mirrors[mirror_id]["sync_count"])
        return True

    def get_primary(self) -> Optional[dict]:
        """Return the primary mirror record, or None if none is configured."""
        with self._lock:
            for record in self._mirrors.values():
                if record["type"] == "primary":
                    return dict(record)
        return None

    def failover(self) -> Optional[dict]:
        """
        Return the highest-priority *online* mirror to use for failover.

        The primary mirror is excluded when it is offline; if it is online it
        is simply the normal target (not a failover candidate in that case).
        """
        with self._lock:
            candidates = [
                r for r in self._mirrors.values()
                if r["status"] == "online" and r["type"] != "primary"
            ]
        if not candidates:
            _logger.warning("failover: no online non-primary mirrors available.")
            return None
        best = max(candidates, key=lambda r: r["priority"])
        _logger.info("failover: selected mirror '%s' (id=%s, priority=%d).", best["name"], best["mirror_id"], best["priority"])
        return dict(best)

    def metrics(self) -> dict:
        """Return counts of mirrors grouped by status and type."""
        with self._lock:
            records = list(self._mirrors.values())

        by_status: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for r in records:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
            by_type[r["type"]] = by_type.get(r["type"], 0) + 1

        return {
            "total": len(records),
            "by_status": by_status,
            "by_type": by_type,
        }
