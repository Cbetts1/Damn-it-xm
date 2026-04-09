# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Governance Audit Log
===========================
The system-wide append-only audit log.

All privileged operations, policy decisions, identity events, and build
pipeline events are written here.  The audit log is owned by ROOT and
cannot be tampered with by HOME-layer processes.

The audit log is in-memory (bounded ring buffer) and is also persisted
to the AURA data directory on flush.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from aura.utils import get_logger, generate_id, utcnow, EVENT_BUS

_logger = get_logger("aura.governance.audit")


class AuditCategory(str, Enum):
    POLICY      = "policy"
    IDENTITY    = "identity"
    BUILD       = "build"
    DEPLOY      = "deploy"
    BOOT        = "boot"
    NETWORK     = "network"
    DEVICE      = "device"
    SHELL       = "shell"
    SYSTEM      = "system"


@dataclass
class AuditEvent:
    """A single immutable audit log event."""

    event_id: str
    ts: str
    category: AuditCategory
    actor: str           # who did this (subject / identity)
    action: str          # what they did
    resource: str        # what resource was affected
    outcome: str         # "allow" | "deny" | "ok" | "error"
    detail: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "category": self.category.value,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "outcome": self.outcome,
            "detail": self.detail,
            "metadata": self.metadata,
        }


class AuditLog:
    """
    System-wide append-only audit log.

    Parameters
    ----------
    max_entries:
        Maximum number of events retained in memory (ring buffer).
    data_dir:
        Directory for persisting the audit log to disk (optional).
    """

    def __init__(
        self,
        max_entries: int = 10000,
        data_dir: Optional[str] = None,
    ) -> None:
        self._events: List[AuditEvent] = []
        self._max = max_entries
        self._data_dir = data_dir
        self._lock = threading.RLock()

        # Subscribe to EventBus events that are worth auditing
        EVENT_BUS.subscribe("root.started",        self._on_system_event)
        EVENT_BUS.subscribe("root.stopped",        self._on_system_event)
        EVENT_BUS.subscribe("boot.complete",       self._on_system_event)
        EVENT_BUS.subscribe("boot.panic",          self._on_system_event)
        EVENT_BUS.subscribe("build.started",       self._on_build_event)
        EVENT_BUS.subscribe("build.deployed",      self._on_build_event)
        EVENT_BUS.subscribe("build.failed",        self._on_build_event)
        EVENT_BUS.subscribe("service.started",     self._on_service_event)
        EVENT_BUS.subscribe("service.failed",      self._on_service_event)

        _logger.info("AuditLog: initialised (max=%d)", max_entries)

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def write(
        self,
        category: AuditCategory,
        actor: str,
        action: str,
        resource: str,
        outcome: str,
        detail: str = "",
        metadata: Optional[dict] = None,
    ) -> AuditEvent:
        """Append an audit event."""
        event = AuditEvent(
            event_id=generate_id("audit"),
            ts=utcnow(),
            category=category,
            actor=actor,
            action=action,
            resource=resource,
            outcome=outcome,
            detail=detail,
            metadata=metadata or {},
        )
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max:
                self._events = self._events[-(self._max):]
        return event

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def query(
        self,
        last_n: int = 100,
        category: Optional[AuditCategory] = None,
        actor: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> List[dict]:
        with self._lock:
            events = list(self._events)
        if category:
            events = [e for e in events if e.category == category]
        if actor:
            events = [e for e in events if e.actor == actor]
        if outcome:
            events = [e for e in events if e.outcome == outcome]
        return [e.to_dict() for e in events[-last_n:]]

    def metrics(self) -> dict:
        with self._lock:
            total = len(self._events)
            by_cat: dict = {}
            by_outcome: dict = {}
            for e in self._events:
                by_cat[e.category.value] = by_cat.get(e.category.value, 0) + 1
                by_outcome[e.outcome] = by_outcome.get(e.outcome, 0) + 1
        return {
            "total_events": total,
            "by_category": by_cat,
            "by_outcome": by_outcome,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def flush_to_disk(self) -> Optional[str]:
        """Flush the audit log to a JSON file.  Returns the file path."""
        if not self._data_dir:
            return None
        os.makedirs(self._data_dir, exist_ok=True)
        path = os.path.join(self._data_dir, "audit.jsonl")
        try:
            with self._lock:
                events = list(self._events)
            with open(path, "w", encoding="utf-8") as fh:
                for event in events:
                    fh.write(json.dumps(event.to_dict()) + "\n")
            _logger.info("AuditLog: flushed %d events to %s", len(events), path)
            return path
        except OSError as exc:
            _logger.error("AuditLog: flush error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # EventBus callbacks
    # ------------------------------------------------------------------

    def _on_system_event(self, event_type: str, payload: dict) -> None:
        self.write(
            AuditCategory.SYSTEM,
            actor="system",
            action=event_type,
            resource="system",
            outcome="ok",
            metadata=payload,
        )

    def _on_build_event(self, event_type: str, payload: dict) -> None:
        outcome = "ok" if "failed" not in event_type else "error"
        self.write(
            AuditCategory.BUILD,
            actor=payload.get("submitter", "build-pipeline"),
            action=event_type,
            resource=f"artefact:{payload.get('artefact_id', '?')}",
            outcome=outcome,
            metadata=payload,
        )

    def _on_service_event(self, event_type: str, payload: dict) -> None:
        outcome = "ok" if "failed" not in event_type else "error"
        self.write(
            AuditCategory.SYSTEM,
            actor="aura-init",
            action=event_type,
            resource=f"service:{payload.get('name', '?')}",
            outcome=outcome,
            metadata=payload,
        )
