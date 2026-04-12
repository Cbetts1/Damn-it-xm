# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Virtual Network Node — node registry (Command Center registration)."""

from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from typing import Optional

from aura.utils import get_logger, utcnow
from aura.vnode.identity import VNodeIdentity

_logger = get_logger("aura.vnode.registry")


class VNodeRegistry:
    """
    Registers this AURa node with a remote Command Center over HTTP.

    If ``command_center_url`` is empty or the server is unreachable the
    methods return ``False`` and log a warning — they never raise.
    """

    def __init__(
        self,
        identity: VNodeIdentity,
        command_center_url: str = "",
        timeout_seconds: int = 5,
    ) -> None:
        self._identity = identity
        self._url = command_center_url.rstrip("/")
        self._timeout = timeout_seconds
        self._lock = threading.RLock()
        self._registered: bool = False
        self._last_error: Optional[str] = None
        _logger.info("VNodeRegistry: command_center_url=%r", self._url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self) -> bool:
        """POST node identity to ``/api/nodes/register``. Returns True on success."""
        return self._post("/api/nodes/register", self._identity.to_dict(), _set_registered=True)

    def deregister(self) -> bool:
        """POST deregistration notice to ``/api/nodes/deregister``. Returns True on success."""
        payload = {"node_id": self._identity.node_id, "timestamp": utcnow()}
        ok = self._post("/api/nodes/deregister", payload, _set_registered=False)
        return ok

    @property
    def is_registered(self) -> bool:
        with self._lock:
            return self._registered

    @property
    def last_error(self) -> Optional[str]:
        with self._lock:
            return self._last_error

    def metrics(self) -> dict:
        with self._lock:
            return {
                "registration_status": "registered" if self._registered else "unregistered",
                "command_center_url": self._url,
                "last_error": self._last_error,
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict, *, _set_registered: Optional[bool] = None) -> bool:
        if not self._url:
            _logger.warning("VNodeRegistry: command_center_url is not configured — skipping %s", path)
            with self._lock:
                self._last_error = "command_center_url not configured"
            return False

        url = self._url + path
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                status = resp.status
            _logger.info("VNodeRegistry: %s → HTTP %s", path, status)
            with self._lock:
                self._last_error = None
                if _set_registered is not None:
                    self._registered = _set_registered
            return True
        except (urllib.error.URLError, OSError, Exception) as exc:
            err = str(exc)
            _logger.warning("VNodeRegistry: %s failed: %s", path, err)
            with self._lock:
                self._last_error = err
            return False
