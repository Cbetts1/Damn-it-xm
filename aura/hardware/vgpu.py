# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa /dev/vgpu — Virtual GPU / Compute Device
===============================================
The /dev/vgpu device is the unified compute interface for all workloads.

Exposes the :class:`~aura.compute.dispatcher.ComputeDispatcher` through
the /dev/ layer with the same open/read/metrics interface as other devices.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, TYPE_CHECKING

from aura.compute.dispatcher import ComputeDispatcher, ComputeBackend
from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.hardware.vcpu import VCPUDevice
    from aura.cloud.virtual_cloud import VirtualCloud

_logger = get_logger("aura.hardware.vgpu")

DEV_PATH = "/dev/vgpu"


class VGPUDevice:
    """
    /dev/vgpu — Virtual GPU / compute dispatcher device.

    Wraps :class:`ComputeDispatcher` and exposes it as a /dev/ device.
    """

    def __init__(
        self,
        vcpu: "VCPUDevice",
        cloud: "VirtualCloud",
        spill_threshold_pct: float = 80.0,
        default_backend: str = "local",
    ) -> None:
        backend = ComputeBackend(default_backend) if default_backend in ("local", "cloud") \
            else ComputeBackend.LOCAL
        self._dispatcher = ComputeDispatcher(
            vcpu=vcpu,
            cloud=cloud,
            spill_threshold_pct=spill_threshold_pct,
            default_backend=backend,
        )
        _logger.info("/dev/vgpu: device ready (default=%s)", default_backend)

    @property
    def path(self) -> str:
        return DEV_PATH

    def submit(
        self,
        fn: Callable,
        name: str = "vgpu-job",
        backend: str = "auto",
    ) -> str:
        """Submit a compute job.  Returns job_id."""
        b = ComputeBackend(backend) if backend in ("local", "cloud", "auto") \
            else ComputeBackend.AUTO
        return self._dispatcher.submit(fn, name=name, backend=b)

    def get_job(self, job_id: str) -> Optional[dict]:
        return self._dispatcher.get_job(job_id)

    def list_jobs(self) -> List[dict]:
        return self._dispatcher.list_jobs()

    def metrics(self) -> dict:
        return self._dispatcher.metrics()

    def status(self) -> str:
        return "online"
