# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Compute Dispatcher — /dev/vgpu
=====================================
Unified compute dispatch layer.  Callers submit work to the dispatcher
without knowing whether it runs locally or in the cloud.

Routing logic:
  1. If local CPU utilisation is below the spill threshold → run locally.
  2. If local CPU is over the threshold → dispatch to cloud.
  3. If the caller explicitly specifies a backend → honour that.

Local backend:  uses the VirtualCPU thread pool (/dev/vcpu).
Cloud backend:  dispatches to a VirtualCloud compute node.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from aura.utils import get_logger, generate_id, utcnow

if TYPE_CHECKING:
    from aura.hardware.vcpu import VCPUDevice
    from aura.cloud.virtual_cloud import VirtualCloud

_logger = get_logger("aura.compute.dispatcher")


class ComputeBackend(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    AUTO  = "auto"      # let the dispatcher decide


class JobStatus(str, Enum):
    QUEUED    = "queued"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


@dataclass
class ComputeJob:
    """A single compute job submitted to /dev/vgpu."""

    job_id: str
    name: str
    backend_used: ComputeBackend
    status: JobStatus
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_ms: float = 0.0
    result: Any = None
    error: Optional[str] = None
    task_id: Optional[str] = None   # underlying VirtualCPU task ID

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "backend_used": self.backend_used.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
            "task_id": self.task_id,
        }


class ComputeDispatcher:
    """
    Unified compute dispatcher exposed as /dev/vgpu.

    Parameters
    ----------
    vcpu:
        The /dev/vcpu device for local dispatch.
    cloud:
        The VirtualCloud for cloud dispatch.
    spill_threshold_pct:
        CPU utilisation (%) above which jobs spill to cloud.
    default_backend:
        Default backend when ``ComputeBackend.AUTO`` is used and
        utilisation cannot be determined.
    """

    def __init__(
        self,
        vcpu: "VCPUDevice",
        cloud: "VirtualCloud",
        spill_threshold_pct: float = 80.0,
        default_backend: ComputeBackend = ComputeBackend.LOCAL,
    ) -> None:
        self._vcpu = vcpu
        self._cloud = cloud
        self._spill_threshold = spill_threshold_pct
        self._default_backend = default_backend
        self._jobs: Dict[str, ComputeJob] = {}
        self._lock = threading.RLock()
        _logger.info(
            "/dev/vgpu: spill_threshold=%.0f%% default=%s",
            spill_threshold_pct, default_backend.value,
        )

    @property
    def path(self) -> str:
        return "/dev/vgpu"

    # ------------------------------------------------------------------
    # Job submission
    # ------------------------------------------------------------------

    def submit(
        self,
        fn: Callable,
        name: str = "compute-job",
        backend: ComputeBackend = ComputeBackend.AUTO,
    ) -> str:
        """
        Submit a callable for execution.

        Parameters
        ----------
        fn:
            Zero-argument callable to execute.
        name:
            Human-readable job name.
        backend:
            ``AUTO`` lets the dispatcher choose; ``LOCAL`` forces the
            VirtualCPU; ``CLOUD`` forces cloud dispatch.

        Returns
        -------
        str
            Job ID.
        """
        resolved = self._resolve_backend(backend)
        job = ComputeJob(
            job_id=generate_id("vgpu"),
            name=name,
            backend_used=resolved,
            status=JobStatus.QUEUED,
            created_at=utcnow(),
        )
        with self._lock:
            self._jobs[job.job_id] = job

        if resolved == ComputeBackend.LOCAL:
            self._submit_local(job, fn)
        else:
            self._submit_cloud(job, fn)

        _logger.info(
            "/dev/vgpu: job %s submitted (backend=%s name=%s)",
            job.job_id, resolved.value, name,
        )
        return job.job_id

    # ------------------------------------------------------------------
    # Job queries
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None

    def list_jobs(self) -> List[dict]:
        with self._lock:
            return [j.to_dict() for j in self._jobs.values()]

    def metrics(self) -> dict:
        with self._lock:
            total = len(self._jobs)
            by_status = {}
            for j in self._jobs.values():
                by_status[j.status.value] = by_status.get(j.status.value, 0) + 1
            local_pct = self._local_cpu_pct()
            return {
                "device": "/dev/vgpu",
                "spill_threshold_pct": self._spill_threshold,
                "local_cpu_pct": local_pct,
                "total_jobs": total,
                "by_status": by_status,
                "active_backend": self._resolve_backend(ComputeBackend.AUTO).value,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_backend(self, requested: ComputeBackend) -> ComputeBackend:
        if requested != ComputeBackend.AUTO:
            return requested
        cpu_pct = self._local_cpu_pct()
        if cpu_pct >= self._spill_threshold:
            _logger.debug(
                "/dev/vgpu: CPU %.1f%% >= threshold %.1f%% → spilling to cloud",
                cpu_pct, self._spill_threshold,
            )
            return ComputeBackend.CLOUD
        return ComputeBackend.LOCAL

    def _local_cpu_pct(self) -> float:
        try:
            m = self._vcpu.metrics()
            workers_active = m.get("workers_active", 0)
            max_tasks = m.get("max_concurrent_tasks", 1) or 1
            return min(100.0, workers_active / max_tasks * 100.0)
        except Exception:
            return 0.0

    def _submit_local(self, job: ComputeJob, fn: Callable) -> None:
        """Submit via /dev/vcpu."""
        def _wrapped():
            job.started_at = utcnow()
            job.status = JobStatus.RUNNING
            t0 = time.monotonic()
            try:
                result = fn()
                job.result = result
                job.status = JobStatus.COMPLETED
            except Exception as exc:
                job.error = str(exc)
                job.status = JobStatus.FAILED
            finally:
                job.finished_at = utcnow()
                job.duration_ms = (time.monotonic() - t0) * 1000.0

        task_id = self._vcpu.submit(_wrapped, name=job.name)
        with self._lock:
            job.task_id = task_id

    def _submit_cloud(self, job: ComputeJob, fn: Callable) -> None:
        """
        Submit to VirtualCloud.  The cloud layer schedules the work on
        an available compute node.  Since VirtualCloud uses the VirtualCPU
        under the hood, we dispatch via the local path but mark it as
        CLOUD for accounting.
        """
        def _cloud_wrapped():
            job.started_at = utcnow()
            job.status = JobStatus.RUNNING
            t0 = time.monotonic()
            try:
                result = fn()
                job.result = result
                job.status = JobStatus.COMPLETED
            except Exception as exc:
                job.error = str(exc)
                job.status = JobStatus.FAILED
            finally:
                job.finished_at = utcnow()
                job.duration_ms = (time.monotonic() - t0) * 1000.0

        task_id = self._vcpu.submit(_cloud_wrapped, name=f"cloud:{job.name}")
        with self._lock:
            job.task_id = task_id
