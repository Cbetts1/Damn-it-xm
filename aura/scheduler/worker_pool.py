# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Scheduler Worker Pool — thread-based execution of TaskRecords."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from aura.scheduler.lifecycle import TaskRecord
from aura.utils import get_logger

_logger = get_logger("aura.scheduler.worker_pool")

_POISON_PILL = object()


class WorkerPool:
    """
    A fixed-size thread pool that executes ``TaskRecord`` callables.

    When a record completes (success or exception) the *on_done* callback
    is invoked with ``(record,)`` so the scheduler can post-process results.
    """

    def __init__(self, worker_count: int = 4) -> None:
        self._worker_count = max(1, worker_count)
        self._queue: queue.Queue = queue.Queue()
        self._workers: list[threading.Thread] = []
        self._active = threading.Semaphore(0)
        self._active_count = 0
        self._count_lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        for i in range(self._worker_count):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"aura-worker-{i}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)
        _logger.info("WorkerPool started with %d workers", self._worker_count)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for _ in self._workers:
            self._queue.put(_POISON_PILL)
        for t in self._workers:
            t.join(timeout=2.0)
        self._workers.clear()
        _logger.info("WorkerPool stopped")

    def submit(self, record: TaskRecord, on_done: Callable) -> None:
        """Enqueue *(record, on_done)* for worker execution."""
        self._queue.put((record, on_done))

    def active_count(self) -> int:
        with self._count_lock:
            return self._active_count

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is _POISON_PILL:
                break
            record, on_done = item
            with self._count_lock:
                self._active_count += 1
            try:
                on_done(record)
            except Exception as exc:
                _logger.error("WorkerPool: unhandled error in on_done: %s", exc)
            finally:
                with self._count_lock:
                    self._active_count -= 1
                self._queue.task_done()
