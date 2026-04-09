# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Scheduler Queue — priority-lane deque with thread-safe pop."""

from __future__ import annotations

import collections
import threading
from typing import Optional

from aura.scheduler.lifecycle import TaskRecord, TaskState
from aura.utils import get_logger

_logger = get_logger("aura.scheduler.queue")

# Priority lanes: 0 = CRITICAL … 4 = BACKGROUND
_NUM_LANES = 5


class SchedulerQueue:
    """
    Priority-lane scheduler queue.

    Each priority level (0–4) has its own ``collections.deque``.
    ``pop()`` always drains the lowest-numbered (highest-priority) lane first.
    """

    def __init__(self) -> None:
        self._lanes: list[collections.deque] = [
            collections.deque() for _ in range(_NUM_LANES)
        ]
        self._lock = threading.Lock()

    def push(self, record: TaskRecord) -> None:
        """Enqueue *record* into the appropriate priority lane."""
        lane = max(0, min(record.priority, _NUM_LANES - 1))
        with self._lock:
            self._lanes[lane].append(record)

    def pop(self) -> Optional[TaskRecord]:
        """Return and remove the highest-priority pending record, or None."""
        with self._lock:
            for lane in self._lanes:
                if lane:
                    return lane.popleft()
        return None

    def size(self) -> int:
        """Total number of tasks across all lanes."""
        with self._lock:
            return sum(len(lane) for lane in self._lanes)

    def cancel(self, task_id: str) -> bool:
        """Mark a queued task as CANCELLED and remove it. Returns True if found."""
        with self._lock:
            for lane in self._lanes:
                for record in lane:
                    if record.task_id == task_id:
                        record.state = TaskState.CANCELLED
                        lane.remove(record)
                        _logger.debug("Scheduler queue: cancelled task %s", task_id)
                        return True
        return False
