# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Scheduler — task lifecycle states and records."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from aura.utils import utcnow


class TaskState(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class TaskRecord:
    """Represents a scheduler task and its full lifecycle."""

    task_id: str
    name: str
    priority: int
    state: TaskState
    user_id: Optional[str]
    ram_mb: float
    cpu_ms: float
    created_at: str
    queued_at: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    error: Optional[str]
    result: Any
    retry_count: int
    max_retries: int
    timeout_seconds: float
    fn: Optional[Callable] = field(default=None, compare=False, repr=False)
    args: tuple = field(default_factory=tuple, compare=False, repr=False)
    kwargs: dict = field(default_factory=dict, compare=False, repr=False)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "priority": self.priority,
            "state": self.state.value,
            "user_id": self.user_id,
            "ram_mb": self.ram_mb,
            "cpu_ms": round(self.cpu_ms, 2),
            "created_at": self.created_at,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
        }

    def duration_ms(self) -> float:
        """Return elapsed milliseconds between started_at and finished_at."""
        if self.started_at is None or self.finished_at is None:
            return 0.0
        from datetime import datetime, timezone
        fmt = "%Y-%m-%dT%H:%M:%S.%f%z" if "." in self.started_at else "%Y-%m-%dT%H:%M:%S%z"
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.finished_at)
            return (end - start).total_seconds() * 1000.0
        except Exception:
            return 0.0
