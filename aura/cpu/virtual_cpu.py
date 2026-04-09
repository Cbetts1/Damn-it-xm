"""
AURa Virtual CPU
================
Manages a pool of virtual compute tasks dispatched by the AI OS.
Provides:
  • Task queue with priority scheduling
  • Worker threads that execute coroutines/callables
  • Real-time metrics (load, queue depth, throughput)
  • CPU affinity simulation across virtual cores

The AI OS routes compute-heavy work (model inference, data processing) through
the Virtual CPU, which can delegate overflow to the Virtual Cloud nodes.
"""

from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from aura.config import CPUConfig
from aura.utils import get_logger, generate_id, utcnow, EVENT_BUS

_logger = get_logger("aura.cpu")

# Maximum number of completed/failed tasks to retain in the task registry.
# Prevents unbounded memory growth on long-running mobile sessions.
_MAX_TASK_HISTORY: int = 2048


class TaskPriority(int, Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(order=True)
class CPUTask:
    priority: int
    task_id: str = field(compare=False)
    name: str = field(compare=False)
    fn: Callable = field(compare=False, repr=False)
    args: tuple = field(default_factory=tuple, compare=False, repr=False)
    kwargs: dict = field(default_factory=dict, compare=False, repr=False)
    status: TaskStatus = field(default=TaskStatus.QUEUED, compare=False)
    result: Any = field(default=None, compare=False)
    error: Optional[str] = field(default=None, compare=False)
    created_at: str = field(default_factory=utcnow, compare=False)
    started_at: Optional[str] = field(default=None, compare=False)
    finished_at: Optional[str] = field(default=None, compare=False)
    duration_ms: float = field(default=0.0, compare=False)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "priority": TaskPriority(self.priority).name,
            "status": self.status.value,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2),
        }


# Sentinel object used to signal worker threads to shut down.
_POISON_PILL = object()


class VirtualCPU:
    """
    The AURa Virtual CPU.
    Manages a thread-pool based task scheduler that the AI OS uses to
    dispatch compute work across virtual cores.
    """

    def __init__(self, config: CPUConfig) -> None:
        self._config = config
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._tasks: Dict[str, CPUTask] = {}
        self._finished_order: List[str] = []  # tracks eviction order
        self._workers: List[threading.Thread] = []
        self._lock = threading.Lock()
        self._running = False
        self._completed_count = 0
        self._failed_count = 0
        self._start_time = time.monotonic()
        self._active_task_count = 0
        self._logger = get_logger("aura.cpu")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        # On mobile / Termux, limit workers to actual host CPUs to save RAM.
        host_cpus = os.cpu_count() or 2
        num_workers = min(
            self._config.virtual_cores,
            self._config.max_concurrent_tasks,
            max(host_cpus, 2),  # never fewer than 2 workers
        )
        for i in range(num_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"aura-vcpu-{i:03d}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        self._logger.info(
            "Virtual CPU started — %d workers (%d vCores @ %.1f GHz)",
            num_workers,
            self._config.virtual_cores,
            self._config.clock_speed_ghz,
        )
        EVENT_BUS.publish("cpu.started", {"workers": num_workers})

    def stop(self) -> None:
        self._running = False
        # Send sentinel for each worker
        for _ in self._workers:
            self._task_queue.put((TaskPriority.CRITICAL.value, _POISON_PILL))
        self._logger.info("Virtual CPU stopped")
        EVENT_BUS.publish("cpu.stopped", {})

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    def submit(
        self,
        fn: Callable,
        name: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        *args,
        **kwargs,
    ) -> str:
        task_id = generate_id("task")
        task = CPUTask(
            priority=priority.value,
            task_id=task_id,
            name=name or fn.__name__,
            fn=fn,
            args=args,
            kwargs=kwargs,
        )
        with self._lock:
            self._tasks[task_id] = task
        self._task_queue.put((priority.value, task))
        EVENT_BUS.publish("cpu.task.submitted", {"task_id": task_id, "name": task.name})
        return task_id

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.QUEUED:
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def get_task(self, task_id: str) -> Optional[dict]:
        with self._lock:
            t = self._tasks.get(task_id)
            return t.to_dict() if t else None

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[dict]:
        with self._lock:
            tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [t.to_dict() for t in tasks]

    # ------------------------------------------------------------------
    # Internal worker
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while self._running:
            try:
                item = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            _priority, task = item
            if task is _POISON_PILL:  # shutdown sentinel
                self._task_queue.task_done()
                break
            if task.status == TaskStatus.CANCELLED:
                self._task_queue.task_done()
                continue

            with self._lock:
                task.status = TaskStatus.RUNNING
                task.started_at = utcnow()
                self._active_task_count += 1

            t0 = time.monotonic()
            try:
                result = task.fn(*task.args, **task.kwargs)
                with self._lock:
                    task.result = result
                    task.status = TaskStatus.COMPLETED
                    self._completed_count += 1
                EVENT_BUS.publish("cpu.task.completed", {"task_id": task.task_id})
            except Exception as exc:
                with self._lock:
                    task.error = str(exc)
                    task.status = TaskStatus.FAILED
                    self._failed_count += 1
                self._logger.error("Task %s failed: %s", task.task_id, exc)
                EVENT_BUS.publish("cpu.task.failed", {"task_id": task.task_id, "error": str(exc)})
            finally:
                elapsed_ms = (time.monotonic() - t0) * 1000
                with self._lock:
                    task.duration_ms = elapsed_ms
                    task.finished_at = utcnow()
                    task.fn = None  # release reference to original callable
                    self._active_task_count -= 1
                    self._finished_order.append(task.task_id)
                    self._evict_old_tasks()
                self._task_queue.task_done()

    def _evict_old_tasks(self) -> None:
        """Remove oldest finished tasks when registry exceeds limit (called under lock)."""
        while len(self._finished_order) > _MAX_TASK_HISTORY:
            old_id = self._finished_order.pop(0)
            self._tasks.pop(old_id, None)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics(self) -> dict:
        with self._lock:
            active = self._active_task_count
            completed = self._completed_count
            failed = self._failed_count
        uptime = time.monotonic() - self._start_time
        return {
            "architecture": self._config.architecture,
            "virtual_cores": self._config.virtual_cores,
            "threads_per_core": self._config.threads_per_core,
            "clock_speed_ghz": self._config.clock_speed_ghz,
            "l3_cache_mb": self._config.cache_l3_mb,
            "workers_active": active,
            "queue_depth": self._task_queue.qsize(),
            "tasks_completed": completed,
            "tasks_failed": failed,
            "throughput_tps": round(completed / uptime, 3) if uptime > 0 else 0,
            "uptime_seconds": round(uptime, 1),
            "running": self._running,
        }
