# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa WorkloadRunner — runs subprocesses via the TaskScheduler."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.scheduler.scheduler import TaskScheduler
    from aura.orchestration.tool_registry import ToolRegistry

_logger = get_logger("aura.orchestration.runner")


@dataclass
class RunResult:
    name: str
    command: str
    returncode: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": round(self.duration_ms, 2),
            "timed_out": self.timed_out,
            "success": self.success,
        }

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class WorkloadRunner:
    """
    Submits subprocess invocations to the ``TaskScheduler`` with resource
    accounting, then synchronously waits for the result.
    """

    def __init__(
        self,
        scheduler: "TaskScheduler",
        registry: "ToolRegistry",
    ) -> None:
        self._scheduler = scheduler
        self._registry = registry

    def run(
        self,
        tool_name: str,
        args: Optional[List[str]] = None,
        cwd: Optional[str] = None,
        timeout: float = 30.0,
        ram_mb: float = 64.0,
        user_id: Optional[str] = None,
    ) -> RunResult:
        """
        Run *tool_name* with *args* as a scheduler task.
        Blocks until the subprocess completes or *timeout* is exceeded.
        Returns a ``RunResult``.
        """
        entry = self._registry.get(tool_name)
        if entry is None:
            _logger.warning("Tool %r not found in registry", tool_name)
            path = tool_name  # fall back to bare command
        else:
            path = entry.path

        cmd_parts = [path] + (args or [])
        command_str = " ".join(cmd_parts)
        result_holder: list = []

        def _run_subprocess():
            t0 = time.monotonic()
            timed_out = False
            try:
                proc = subprocess.run(
                    cmd_parts,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=timeout,
                )
                elapsed = (time.monotonic() - t0) * 1000.0
                return RunResult(
                    name=tool_name,
                    command=command_str,
                    returncode=proc.returncode,
                    stdout=proc.stdout or "",
                    stderr=proc.stderr or "",
                    duration_ms=elapsed,
                    timed_out=False,
                )
            except subprocess.TimeoutExpired:
                elapsed = (time.monotonic() - t0) * 1000.0
                return RunResult(
                    name=tool_name,
                    command=command_str,
                    returncode=-1,
                    stdout="",
                    stderr="Timed out",
                    duration_ms=elapsed,
                    timed_out=True,
                )
            except Exception as exc:
                elapsed = (time.monotonic() - t0) * 1000.0
                return RunResult(
                    name=tool_name,
                    command=command_str,
                    returncode=-1,
                    stdout="",
                    stderr=str(exc),
                    duration_ms=elapsed,
                    timed_out=False,
                )

        # Submit to scheduler and wait for completion by running directly
        # (scheduler wraps the function and runs it on VirtualCPU worker)
        task_id = self._scheduler.submit(
            _run_subprocess,
            name=f"run:{tool_name}",
            ram_mb=ram_mb,
            timeout_seconds=timeout,
            user_id=user_id,
        )

        # Wait for the task to finish with polling
        deadline = time.monotonic() + timeout + 5.0  # generous wait
        while time.monotonic() < deadline:
            t = self._scheduler.get_task(task_id)
            if t and t["state"] in ("completed", "failed", "cancelled", "timeout"):
                break
            time.sleep(0.05)

        # Retrieve the result — the CPU task stores return value on the record
        with self._scheduler._lock:
            record = self._scheduler._records.get(task_id)

        if record and record.result is not None:
            return record.result

        # Fallback: run synchronously if result not captured
        return _run_subprocess()
