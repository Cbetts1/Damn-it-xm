# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Virtual Network Node — node identity."""

from __future__ import annotations

import hashlib
import os
import platform
import threading
from typing import List

from aura.utils import get_logger, utcnow

_VERSION = "2.0.0"
_NODE_ID_FILE = os.path.expanduser("~/.aura/node_id")

_logger = get_logger("aura.vnode.identity")


def _load_or_create_node_id() -> str:
    """Load persisted node_id from disk, creating it on first run."""
    import uuid

    if os.path.isfile(_NODE_ID_FILE):
        try:
            with open(_NODE_ID_FILE, "r", encoding="utf-8") as fh:
                nid = fh.read().strip()
            if nid:
                return nid
        except OSError as exc:
            _logger.warning("VNodeIdentity: could not read node_id file: %s", exc)

    nid = str(uuid.uuid4())
    try:
        os.makedirs(os.path.dirname(_NODE_ID_FILE), exist_ok=True)
        with open(_NODE_ID_FILE, "w", encoding="utf-8") as fh:
            fh.write(nid)
        _logger.info("VNodeIdentity: new node_id persisted to %s", _NODE_ID_FILE)
    except OSError as exc:
        _logger.warning("VNodeIdentity: could not persist node_id: %s", exc)

    return nid


def _detect_platform() -> str:
    if os.path.exists("/data/data/com.termux"):
        return "termux/android"
    system = platform.system().lower()
    if system == "linux":
        return "linux"
    return "unknown"


class VNodeIdentity:
    """
    Stable virtual identity for an AURa installation.

    The ``node_id`` is generated once (UUID4) and persisted to
    ``~/.aura/node_id`` so it survives restarts.
    """

    def __init__(
        self,
        node_name: str = "aura-node",
        capabilities: List[str] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self.node_id: str = _load_or_create_node_id()
        self.node_name: str = node_name
        self.capabilities: List[str] = capabilities or [
            "ai_engine",
            "build",
            "metrics",
            "shell",
            "web_api",
        ]
        self.version: str = _VERSION
        self.platform: str = _detect_platform()
        self.created_at: str = utcnow()
        _logger.info(
            "VNodeIdentity: node_id=%s  platform=%s", self.node_id, self.platform
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def refresh_platform(self) -> str:
        """Re-detect and update the platform string."""
        with self._lock:
            self.platform = _detect_platform()
        return self.platform

    def fingerprint(self) -> str:
        """Return a SHA-256 hex digest of ``node_id + version``."""
        raw = (self.node_id + self.version).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "node_id": self.node_id,
                "node_name": self.node_name,
                "capabilities": list(self.capabilities),
                "version": self.version,
                "platform": self.platform,
                "created_at": self.created_at,
                "fingerprint": self.fingerprint(),
            }

    def metrics(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_name": self.node_name,
            "platform": self.platform,
            "version": self.version,
            "capabilities_count": len(self.capabilities),
        }
