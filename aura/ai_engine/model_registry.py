# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Model Registry
===================
Central registry for AI model records.  Thread-safe.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.ai_engine.model_registry")

_VALID_STATUSES = {"available", "loading", "ready", "error"}


class ModelRegistry:
    """Registry that tracks all AI model records known to AURa."""

    def __init__(self) -> None:
        self._models: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._seed_builtin()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _seed_builtin(self) -> None:
        self.register(
            name="aura-builtin-1.0",
            backend="builtin",
            version="1.0.0",
            capabilities=["chat", "plan", "analyse"],
            tags=["builtin", "offline", "default"],
            size_bytes=0,
        )
        # Mark it ready immediately
        with self._lock:
            for record in self._models.values():
                if record["name"] == "aura-builtin-1.0":
                    record["status"] = "ready"
                    break
        _logger.debug("Seeded built-in model 'aura-builtin-1.0'.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        backend: str,
        version: str = "1.0.0",
        capabilities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        size_bytes: int = 0,
    ) -> str:
        """Register a new model and return its model_id."""
        model_id = generate_id("model")
        record = {
            "model_id": model_id,
            "name": name,
            "backend": backend,
            "version": version,
            "status": "available",
            "size_bytes": size_bytes,
            "capabilities": list(capabilities or []),
            "tags": list(tags or []),
            "created_at": utcnow(),
        }
        with self._lock:
            self._models[model_id] = record
        _logger.info("Registered model '%s' (id=%s, backend=%s).", name, model_id, backend)
        return model_id

    def get(self, model_id: str) -> Optional[dict]:
        """Return a model record by id, or None."""
        with self._lock:
            record = self._models.get(model_id)
            return dict(record) if record else None

    def get_by_name(self, name: str) -> Optional[dict]:
        """Return the first model record matching *name*, or None."""
        with self._lock:
            for record in self._models.values():
                if record["name"] == name:
                    return dict(record)
        return None

    def list_models(
        self,
        backend: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[dict]:
        """Return model records, optionally filtered by backend and/or status."""
        with self._lock:
            records = list(self._models.values())
        if backend is not None:
            records = [r for r in records if r["backend"] == backend]
        if status is not None:
            records = [r for r in records if r["status"] == status]
        return [dict(r) for r in records]

    def update_status(self, model_id: str, status: str) -> bool:
        """Update the status of a model.  Returns False if model_id unknown."""
        if status not in _VALID_STATUSES:
            _logger.warning("update_status: invalid status '%s'.", status)
            return False
        with self._lock:
            if model_id not in self._models:
                return False
            self._models[model_id]["status"] = status
        _logger.debug("Model %s status -> '%s'.", model_id, status)
        return True

    def unregister(self, model_id: str) -> bool:
        """Remove a model from the registry.  Returns False if not found."""
        with self._lock:
            if model_id not in self._models:
                return False
            name = self._models.pop(model_id)["name"]
        _logger.info("Unregistered model '%s' (id=%s).", name, model_id)
        return True

    def count(self) -> int:
        """Return the total number of registered models."""
        with self._lock:
            return len(self._models)
