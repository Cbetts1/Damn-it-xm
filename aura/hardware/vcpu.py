# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa /dev/vcpu — Virtual CPU Device
=====================================
ROOT-gated interface to the underlying :class:`VirtualCPU` task scheduler.

Exposes scheduling, metrics, and task management through the /dev/ layer.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.cpu.virtual_cpu import VirtualCPU, TaskPriority

_logger = get_logger("aura.hardware.vcpu")

DEV_PATH = "/dev/vcpu"


class VCPUDevice:
    """
    /dev/vcpu — Virtual CPU device.

    Wraps the :class:`~aura.cpu.virtual_cpu.VirtualCPU` and exposes a
    standardised /dev/ interface.

    Parameters
    ----------
    cpu:
        The underlying VirtualCPU instance.
    """

    def __init__(self, cpu: "VirtualCPU") -> None:
        self._cpu = cpu
        self._lock = threading.RLock()
        _logger.info("/dev/vcpu: device ready (%d vCores)", cpu._config.virtual_cores)

    @property
    def path(self) -> str:
        return DEV_PATH

    def submit(
        self,
        fn: Callable,
        name: str = "task",
        priority: Optional["TaskPriority"] = None,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Submit a callable to the CPU task queue.  Returns task_id."""
        from aura.cpu.virtual_cpu import TaskPriority as TP
        p = priority if priority is not None else TP.NORMAL
        return self._cpu.submit(fn, name=name, priority=p, *args, **kwargs)

    def get_task(self, task_id: str) -> Optional[dict]:
        """Return the task dict for *task_id*, or None."""
        return self._cpu.get_task(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[dict]:
        """List all tasks, optionally filtered by status string."""
        return self._cpu.list_tasks(status=status)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued task.  Returns True if cancelled."""
        return self._cpu.cancel_task(task_id)

    def metrics(self) -> dict:
        """Return current vCPU metrics."""
        m = self._cpu.metrics()
        m["device"] = DEV_PATH
        return m

    def status(self) -> str:
        """Return 'running' or 'stopped'."""
        return "running" if self._cpu._running else "stopped"
