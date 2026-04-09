# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa TaskScheduler — resource-aware wrapper around VirtualCPU."""

from __future__ import annotations

import time
import threading
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from aura.cpu.virtual_cpu import VirtualCPU, TaskPriority
from aura.resources.ram import VirtualRAM
from aura.resources.ledger import ResourceLedger
from aura.resources.quota import QuotaEnforcer
from aura.scheduler.lifecycle import TaskRecord, TaskState
from aura.utils import get_logger, generate_id, utcnow, EVENT_BUS

_logger = get_logger("aura.scheduler")


class TaskScheduler:
    """
    Resource-aware task scheduler that wraps ``VirtualCPU``.

    Adds:
    • Per-task RAM allocation / release
    • Quota checking (soft — warns but does not block)
    • Ledger recording for cost attribution
    • EventBus events: scheduler.task.submitted / completed / failed
    """

    def __init__(
        self,
        cpu: VirtualCPU,
        ram: VirtualRAM,
        ledger: ResourceLedger,
        quota: QuotaEnforcer,
    ) -> None:
        self._cpu = cpu
        self._ram = ram
        self._ledger = ledger
        self._quota = quota
        self._records: Dict[str, TaskRecord] = {}
        self._lock = threading.Lock()
        self._running = False
        _logger.info("TaskScheduler initialised")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        _logger.info("TaskScheduler started")

    def stop(self) -> None:
        self._running = False
        _logger.info("TaskScheduler stopped")

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    def submit(
        self,
        fn: Callable,
        name: str = "",
        priority: int = TaskPriority.NORMAL,
        ram_mb: float = 0.0,
        timeout_seconds: float = 0.0,
        user_id: Optional[str] = None,
        max_retries: int = 3,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """
        Submit a callable to the scheduler.  Returns the task_id.

        The callable is wrapped so that ledger entries are recorded and
        RAM is released on completion.
        """
        task_id = generate_id("sched")
        priority_int = int(priority)

        record = TaskRecord(
            task_id=task_id,
            name=name or fn.__name__ if callable(fn) else "task",
            priority=priority_int,
            state=TaskState.PENDING,
            user_id=user_id,
            ram_mb=ram_mb,
            cpu_ms=0.0,
            created_at=utcnow(),
            queued_at=None,
            started_at=None,
            finished_at=None,
            error=None,
            result=None,
            retry_count=0,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            fn=fn,
            args=args,
            kwargs=kwargs,
        )

        # Quota check (soft)
        ok, reason = self._quota.check(user_id or "system", ram_mb)
        if not ok:
            _logger.warning("Quota warning for task %s: %s", task_id, reason)

        # RAM allocation (soft)
        if ram_mb > 0:
            allocated = self._ram.allocate(task_id, ram_mb)
            if not allocated:
                _logger.warning(
                    "RAM allocation failed for task %s (%.1f MB) — proceeding anyway",
                    task_id,
                    ram_mb,
                )

        # Track in quota enforcer
        self._quota.increment_tasks(user_id or "system")

        # Record in ledger
        self._ledger.record_start(task_id, record.name, user_id, ram_mb)

        # Store record
        with self._lock:
            self._records[task_id] = record

        record.state = TaskState.QUEUED
        record.queued_at = utcnow()

        # Build wrapper
        def _wrapper(_task_id=task_id, _record=record, _fn=fn, _a=args, _kw=kwargs):
            _record.state = TaskState.RUNNING
            _record.started_at = utcnow()
            t0 = time.monotonic()
            try:
                result = _fn(*_a, **_kw)
                elapsed_ms = (time.monotonic() - t0) * 1000.0
                _record.result = result
                _record.cpu_ms = elapsed_ms
                _record.state = TaskState.COMPLETED
                _record.finished_at = utcnow()
                self._ledger.record_finish(_task_id, "completed", elapsed_ms)
                self._ram.release(_task_id)
                self._quota.decrement_tasks(_record.user_id or "system")
                EVENT_BUS.publish(
                    "scheduler.task.completed",
                    {"task_id": _task_id, "name": _record.name, "cpu_ms": elapsed_ms},
                )
                return result
            except Exception as exc:
                elapsed_ms = (time.monotonic() - t0) * 1000.0
                _record.error = str(exc)
                _record.cpu_ms = elapsed_ms
                _record.state = TaskState.FAILED
                _record.finished_at = utcnow()
                self._ledger.record_finish(_task_id, "failed", elapsed_ms)
                self._ram.release(_task_id)
                self._quota.decrement_tasks(_record.user_id or "system")
                EVENT_BUS.publish(
                    "scheduler.task.failed",
                    {"task_id": _task_id, "name": _record.name, "error": str(exc)},
                )
                raise

        # Submit to VirtualCPU
        cpu_task_id = self._cpu.submit(_wrapper, name=record.name, priority=priority_int)
        record.task_id = task_id  # keep our own id

        EVENT_BUS.publish(
            "scheduler.task.submitted",
            {"task_id": task_id, "name": record.name, "ram_mb": ram_mb},
        )

        _logger.debug("Task submitted: %s (cpu_task=%s)", task_id, cpu_task_id)
        return task_id

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def cancel(self, task_id: str) -> bool:
        """Attempt to cancel a task. Returns True if found and cancelled."""
        with self._lock:
            record = self._records.get(task_id)
        if record is None:
            return False
        if record.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            return False
        record.state = TaskState.CANCELLED
        record.finished_at = utcnow()
        self._ram.release(task_id)
        self._quota.decrement_tasks(record.user_id or "system")
        self._ledger.record_finish(task_id, "cancelled")
        return True

    def get_task(self, task_id: str) -> Optional[dict]:
        with self._lock:
            record = self._records.get(task_id)
        return record.to_dict() if record else None

    def list_tasks(
        self, status: Optional[str] = None, limit: int = 50
    ) -> List[dict]:
        with self._lock:
            records = list(self._records.values())
        if status:
            records = [r for r in records if r.state.value == status]
        records = records[-limit:]
        records.reverse()
        return [r.to_dict() for r in records]

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics(self) -> dict:
        with self._lock:
            all_records = list(self._records.values())
        by_state: Dict[str, int] = {}
        for r in all_records:
            by_state[r.state.value] = by_state.get(r.state.value, 0) + 1
        return {
            "total_submitted": len(all_records),
            "by_state": by_state,
            "running": by_state.get("running", 0),
            "pending": by_state.get("pending", 0) + by_state.get("queued", 0),
            "completed": by_state.get("completed", 0),
            "failed": by_state.get("failed", 0),
        }
