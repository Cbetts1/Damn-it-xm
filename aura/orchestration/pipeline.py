# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Pipeline — sequential multi-step workload orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.orchestration.runner import WorkloadRunner

_logger = get_logger("aura.orchestration.pipeline")


@dataclass
class PipelineStep:
    name: str
    tool: str
    args: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    timeout: float = 30.0
    continue_on_error: bool = False


@dataclass
class PipelineResult:
    name: str
    steps: List[dict]
    success: bool
    duration_ms: float

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "steps": self.steps,
            "success": self.success,
            "duration_ms": round(self.duration_ms, 2),
        }


class Pipeline:
    """Runs a sequence of ``PipelineStep`` objects via a ``WorkloadRunner``."""

    def __init__(
        self,
        name: str,
        steps: List[PipelineStep],
        runner: "WorkloadRunner",
    ) -> None:
        self._name = name
        self._steps = steps
        self._runner = runner

    def run(self) -> PipelineResult:
        _logger.info("Pipeline %r starting (%d steps)", self._name, len(self._steps))
        t0 = time.monotonic()
        step_results = []
        overall_success = True

        for step in self._steps:
            _logger.debug("Pipeline %r: running step %r", self._name, step.name)
            result = self._runner.run(
                tool_name=step.tool,
                args=step.args,
                cwd=step.cwd,
                timeout=step.timeout,
            )
            step_results.append(result.to_dict())
            if not result.success:
                overall_success = False
                _logger.warning(
                    "Pipeline %r: step %r failed (rc=%d)",
                    self._name,
                    step.name,
                    result.returncode,
                )
                if not step.continue_on_error:
                    break

        elapsed_ms = (time.monotonic() - t0) * 1000.0
        _logger.info(
            "Pipeline %r finished: success=%s  %.0f ms",
            self._name,
            overall_success,
            elapsed_ms,
        )
        return PipelineResult(
            name=self._name,
            steps=step_results,
            success=overall_success,
            duration_ms=elapsed_ms,
        )

    @classmethod
    def from_dict(cls, data: dict, runner: "WorkloadRunner") -> "Pipeline":
        """Construct a Pipeline from a dict specification."""
        steps = []
        for s in data.get("steps", []):
            steps.append(
                PipelineStep(
                    name=s.get("name", "step"),
                    tool=s.get("tool", ""),
                    args=s.get("args", []),
                    cwd=s.get("cwd"),
                    timeout=float(s.get("timeout", 30.0)),
                    continue_on_error=bool(s.get("continue_on_error", False)),
                )
            )
        return cls(name=data.get("name", "pipeline"), steps=steps, runner=runner)
