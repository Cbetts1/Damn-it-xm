# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Virtual Network Node — periodic heartbeat service."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
import urllib.error
from typing import Optional

from aura.utils import get_logger, utcnow
from aura.vnode.identity import VNodeIdentity

_logger = get_logger("aura.vnode.heartbeat")


class HeartbeatService:
    """
    Sends a periodic HTTP heartbeat POST to the Command Center.

    The background thread is a daemon thread so it never blocks process exit.
    If the Command Center is unreachable the beat is silently skipped and
    ``last_error`` is updated.
    """

    def __init__(
        self,
        identity: VNodeIdentity,
        command_center_url: str = "",
        interval_seconds: float = 30.0,
    ) -> None:
        self._identity = identity
        self._url = command_center_url.rstrip("/")
        self._interval = interval_seconds
        self._lock = threading.RLock()
        self._running: bool = False
        self._beat_count: int = 0
        self._last_beat_at: Optional[str] = None
        self._last_error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        _logger.info(
            "HeartbeatService: interval=%.1fs  url=%r",
            self._interval,
            self._url,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background heartbeat thread (idempotent)."""
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            name="aura-heartbeat",
            daemon=True,
        )
        self._thread.start()
        _logger.info("HeartbeatService: started")

    def stop(self) -> None:
        """Signal the heartbeat thread to stop."""
        with self._lock:
            self._running = False
        _logger.info("HeartbeatService: stopped")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def beat_count(self) -> int:
        with self._lock:
            return self._beat_count

    @property
    def last_beat_at(self) -> Optional[str]:
        with self._lock:
            return self._last_beat_at

    def metrics(self) -> dict:
        with self._lock:
            return {
                "is_running": self._running,
                "beat_count": self._beat_count,
                "last_beat_at": self._last_beat_at,
                "last_error": self._last_error,
                "interval_seconds": self._interval,
                "command_center_url": self._url,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
            self._beat()
            # Sleep in small increments so stop() is noticed promptly
            elapsed = 0.0
            step = 0.5
            while elapsed < self._interval:
                with self._lock:
                    if not self._running:
                        return
                time.sleep(step)
                elapsed += step

    def _beat(self) -> None:
        if not self._url:
            return

        payload = {
            "node_id": self._identity.node_id,
            "timestamp": utcnow(),
            "status": "ok",
        }
        url = self._url + "/api/nodes/heartbeat"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                _logger.debug("HeartbeatService: beat → HTTP %s", resp.status)
            with self._lock:
                self._beat_count += 1
                self._last_beat_at = utcnow()
                self._last_error = None
        except (urllib.error.URLError, OSError, Exception) as exc:
            err = str(exc)
            _logger.warning("HeartbeatService: beat failed: %s", err)
            with self._lock:
                self._last_error = err
