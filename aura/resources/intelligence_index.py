# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Intelligence Index
=======================
Stores detailed capability, safety, and performance metadata for AI models
known to the AURa ecosystem.  Thread-safe.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.resources.intelligence_index")


class IntelligenceIndex:
    """Registry of AI model intelligence records with filtering and comparison."""

    def __init__(self) -> None:
        self._entries: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._seed_builtin()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _seed_builtin(self) -> None:
        self.register(
            model_name="aura-builtin-1.0",
            backend="builtin",
            version="1.0.0",
            capabilities=["chat", "plan", "analyse"],
            safety_rating=9.0,
            performance_score=65.0,
            provenance="builtin",
            parameters_billions=0.0,
            context_length=2048,
            languages=["en"],
        )
        _logger.debug("Seeded built-in intelligence entry 'aura-builtin-1.0'.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(
        self,
        model_name: str,
        backend: str,
        version: str,
        capabilities: Optional[List[str]] = None,
        safety_rating: float = 8.0,
        performance_score: float = 70.0,
        provenance: str = "builtin",
        parameters_billions: float = 0.0,
        context_length: int = 2048,
        languages: Optional[List[str]] = None,
    ) -> str:
        """Register a new intelligence entry and return its entry_id."""
        entry_id = generate_id("intel")
        record: dict = {
            "entry_id": entry_id,
            "model_name": model_name,
            "backend": backend,
            "version": version,
            "capabilities": list(capabilities or []),
            "safety_rating": float(safety_rating),
            "performance_score": float(performance_score),
            "provenance": provenance,
            "parameters_billions": float(parameters_billions),
            "context_length": int(context_length),
            "languages": list(languages or ["en"]),
            "benchmarks": {},
            "last_evaluated": utcnow(),
            "notes": "",
        }
        with self._lock:
            self._entries[entry_id] = record
        _logger.info("Registered intelligence entry '%s' (id=%s).", model_name, entry_id)
        return entry_id

    def get(self, entry_id: str) -> Optional[dict]:
        """Return an entry by id, or None."""
        with self._lock:
            record = self._entries.get(entry_id)
            return dict(record) if record else None

    def get_by_name(self, model_name: str) -> Optional[dict]:
        """Return the first entry matching *model_name*, or None."""
        with self._lock:
            for record in self._entries.values():
                if record["model_name"] == model_name:
                    return dict(record)
        return None

    def list_entries(
        self,
        min_safety: Optional[float] = None,
        min_performance: Optional[float] = None,
        capability: Optional[str] = None,
    ) -> List[dict]:
        """Return entries with optional filters applied."""
        with self._lock:
            records = list(self._entries.values())
        if min_safety is not None:
            records = [r for r in records if r["safety_rating"] >= min_safety]
        if min_performance is not None:
            records = [r for r in records if r["performance_score"] >= min_performance]
        if capability is not None:
            records = [r for r in records if capability in r["capabilities"]]
        return [dict(r) for r in records]

    def update_benchmark(self, entry_id: str, benchmark_name: str, score: Any) -> bool:
        """Add or update a benchmark score for an entry."""
        with self._lock:
            if entry_id not in self._entries:
                return False
            self._entries[entry_id]["benchmarks"][benchmark_name] = score
            self._entries[entry_id]["last_evaluated"] = utcnow()
        _logger.debug("Benchmark '%s' updated for entry %s.", benchmark_name, entry_id)
        return True

    def update_safety(self, entry_id: str, rating: float) -> bool:
        """Update the safety_rating for an entry."""
        with self._lock:
            if entry_id not in self._entries:
                return False
            self._entries[entry_id]["safety_rating"] = float(rating)
            self._entries[entry_id]["last_evaluated"] = utcnow()
        _logger.debug("Safety rating updated for entry %s -> %.1f.", entry_id, rating)
        return True

    def compare(self, entry_id_a: str, entry_id_b: str) -> dict:
        """
        Compare two entries.

        Returns a dict with per-field deltas (a minus b) and an overall
        *winner* key ("a", "b", or "tie") based on performance_score.
        """
        a = self.get(entry_id_a)
        b = self.get(entry_id_b)
        if a is None or b is None:
            missing = entry_id_a if a is None else entry_id_b
            _logger.warning("compare: entry not found: %s.", missing)
            return {"error": f"entry not found: {missing}"}

        numeric_fields = ("safety_rating", "performance_score", "parameters_billions", "context_length")
        deltas = {field: a[field] - b[field] for field in numeric_fields}

        perf_delta = deltas["performance_score"]
        if perf_delta > 0:
            winner = "a"
        elif perf_delta < 0:
            winner = "b"
        else:
            winner = "tie"

        return {
            "a": a["model_name"],
            "b": b["model_name"],
            "winner": winner,
            "deltas": deltas,
        }

    def top_n(self, n: int = 5, sort_by: str = "performance_score") -> List[dict]:
        """Return the top *n* entries sorted descending by *sort_by* field."""
        with self._lock:
            records = list(self._entries.values())
        try:
            records.sort(key=lambda r: r.get(sort_by, 0), reverse=True)
        except TypeError:
            _logger.warning("top_n: cannot sort by field '%s'.", sort_by)
        return [dict(r) for r in records[:n]]

    def unregister(self, entry_id: str) -> bool:
        """Remove an entry.  Returns False if not found."""
        with self._lock:
            if entry_id not in self._entries:
                return False
            name = self._entries.pop(entry_id)["model_name"]
        _logger.info("Unregistered intelligence entry '%s' (id=%s).", name, entry_id)
        return True
