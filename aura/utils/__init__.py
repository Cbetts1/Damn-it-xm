# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Utilities — shared helpers used across all subsystems."""

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Return a consistently-formatted logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


def generate_id(prefix: str = "") -> str:
    """Generate a unique identifier with optional prefix."""
    uid = str(uuid.uuid4()).replace("-", "")[:12]
    return f"{prefix}-{uid}" if prefix else uid


def utcnow() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str) -> str:
    """Create directory if it doesn't exist; return the path."""
    os.makedirs(path, exist_ok=True)
    return path


def format_bytes(num_bytes: float) -> str:
    """Human-readable byte size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def format_uptime(seconds: float) -> str:
    """Human-readable uptime from seconds."""
    hours, rem = divmod(int(seconds), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}h {minutes:02d}m {secs:02d}s"


class EventBus:
    """
    Lightweight in-process publish/subscribe event bus.
    Used by the AI OS to coordinate messages between virtual components.

    Thread-safe: a lock protects the subscriber list so that publish,
    subscribe, and unsubscribe can be called from any thread.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()
        self._logger = get_logger("aura.eventbus")

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    cb for cb in self._subscribers[event_type] if cb != callback
                ]

    def publish(self, event_type: str, payload: Any = None) -> None:
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))
        self._logger.debug("Event: %s payload=%s", event_type, payload)
        for cb in handlers:
            try:
                cb(event_type, payload)
            except Exception as exc:
                self._logger.error("Event handler error (%s): %s", event_type, exc)

    def publish_all(self, event_type: str, payload: Any = None) -> None:
        self.publish(event_type, payload)
        self.publish("*", {"event": event_type, "payload": payload})


# Global event bus shared across all AURa components
EVENT_BUS = EventBus()
