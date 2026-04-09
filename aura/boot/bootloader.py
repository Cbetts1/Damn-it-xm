# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Bootloader
================
Implements the AURA OS boot chain:

  firmware/bootloader
      └─► ROOT  (claims /dev/* devices, enforces policy)
            └─► mount HOME  (userland filesystem attached R/W)
                  └─► aura-init  (PID-1 equivalent — starts all services)
                        └─► shell  (AURA shell drops operator into session)

The Bootloader orchestrates stages 0→4 and hands off to :class:`AURAInit`
for service start-up.  It records timing for each stage and produces a
structured boot log.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, TYPE_CHECKING

from aura.utils import get_logger, utcnow, EVENT_BUS

if TYPE_CHECKING:
    from aura.root.sovereign import ROOTLayer
    from aura.home.userland import HOMELayer
    from aura.boot.aura_init import AURAInit

_logger = get_logger("aura.boot")


class BootStage(str, Enum):
    FIRMWARE     = "firmware"       # 0 — hardware power-on
    ROOT         = "root"           # 1 — ROOT layer online
    DEVICES      = "devices"        # 2 — /dev/* claimed
    HOME_MOUNT   = "home_mount"     # 3 — HOME userland mounted
    AURA_INIT    = "aura_init"      # 4 — services started
    SHELL        = "shell"          # 5 — operator shell ready
    RUNNING      = "running"        # steady-state


class BootState(str, Enum):
    COLD    = "cold"       # not started
    BOOTING = "booting"
    READY   = "ready"
    HALTING = "halting"
    HALTED  = "halted"
    PANIC   = "panic"      # boot failure


@dataclass
class BootRecord:
    """Timing record for a single boot stage."""
    stage: BootStage
    started_at: str
    finished_at: Optional[str] = None
    duration_ms: float = 0.0
    success: bool = True
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "detail": self.detail,
        }


class Bootloader:
    """
    AURA OS Bootloader.

    Orchestrates the five-stage boot sequence and hands off to AURAInit.

    Parameters
    ----------
    root:
        The ROOT sovereign layer instance (must be created before the
        bootloader starts).
    home:
        The HOME userland layer instance.
    aura_init:
        The PID-1 service manager.
    """

    def __init__(
        self,
        root: "ROOTLayer",
        home: "HOMELayer",
        aura_init: "AURAInit",
    ) -> None:
        self._root = root
        self._home = home
        self._aura_init = aura_init
        self._state = BootState.COLD
        self._current_stage: Optional[BootStage] = None
        self._boot_log: List[BootRecord] = []
        self._boot_start: Optional[float] = None
        _logger.info("Bootloader created (state=COLD)")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> BootState:
        return self._state

    @property
    def current_stage(self) -> Optional[BootStage]:
        return self._current_stage

    @property
    def boot_log(self) -> List[dict]:
        return [r.to_dict() for r in self._boot_log]

    # ------------------------------------------------------------------
    # Boot sequence
    # ------------------------------------------------------------------

    def boot(self) -> None:
        """
        Execute the full boot sequence.

        Raises
        ------
        RuntimeError
            If any non-recoverable stage fails (boot panic).
        """
        if self._state != BootState.COLD:
            _logger.warning("boot() called in state %s — ignoring", self._state.value)
            return

        self._state = BootState.BOOTING
        self._boot_start = time.monotonic()
        _logger.info("=" * 60)
        _logger.info("  AURa OS BOOT SEQUENCE STARTING")
        _logger.info("=" * 60)
        EVENT_BUS.publish("boot.started", {"ts": utcnow()})

        try:
            # Stage 0: Firmware / platform check
            self._run_stage(BootStage.FIRMWARE, self._stage_firmware)

            # Stage 1: ROOT layer online
            self._run_stage(BootStage.ROOT, self._stage_root)

            # Stage 2: Claim /dev/* devices
            self._run_stage(BootStage.DEVICES, self._stage_devices)

            # Stage 3: Mount HOME userland
            self._run_stage(BootStage.HOME_MOUNT, self._stage_home_mount)

            # Stage 4: aura-init — start all services
            self._run_stage(BootStage.AURA_INIT, self._stage_aura_init)

            # Stage 5: Shell ready
            self._run_stage(BootStage.SHELL, self._stage_shell)

        except Exception as exc:
            self._state = BootState.PANIC
            _logger.critical("BOOT PANIC: %s", exc)
            EVENT_BUS.publish("boot.panic", {"error": str(exc)})
            raise RuntimeError(f"Boot panic: {exc}") from exc

        self._state = BootState.READY
        elapsed = (time.monotonic() - self._boot_start) * 1000
        _logger.info("=" * 60)
        _logger.info("  AURa OS BOOT COMPLETE  (%.0f ms)", elapsed)
        _logger.info("=" * 60)
        EVENT_BUS.publish("boot.complete", {
            "elapsed_ms": round(elapsed, 2),
            "ts": utcnow(),
        })

    def halt(self) -> None:
        """Gracefully halt the OS (reverse of boot)."""
        if self._state in (BootState.HALTING, BootState.HALTED, BootState.COLD):
            return
        self._state = BootState.HALTING
        _logger.info("AURa OS HALTING…")
        EVENT_BUS.publish("boot.halting", {"ts": utcnow()})

        try:
            self._aura_init.stop_all()
        except Exception as exc:
            _logger.warning("halt: aura-init stop error: %s", exc)

        try:
            self._root.unmount_home()
        except Exception as exc:
            _logger.warning("halt: HOME unmount error: %s", exc)

        try:
            self._root.stop()
        except Exception as exc:
            _logger.warning("halt: ROOT stop error: %s", exc)

        self._state = BootState.HALTED
        EVENT_BUS.publish("boot.halted", {"ts": utcnow()})
        _logger.info("AURa OS HALTED.")

    # ------------------------------------------------------------------
    # Boot stages
    # ------------------------------------------------------------------

    def _stage_firmware(self) -> None:
        """Stage 0: Detect hardware / firmware environment."""
        import platform, os
        _logger.info(
            "[BOOT 0/5] Firmware: platform=%s arch=%s python=%s",
            platform.system(), platform.machine(), platform.python_version(),
        )

    def _stage_root(self) -> None:
        """Stage 1: Bring ROOT layer online."""
        _logger.info("[BOOT 1/5] ROOT: bringing sovereign layer online…")
        self._root.start()
        _logger.info("[BOOT 1/5] ROOT: online")

    def _stage_devices(self) -> None:
        """Stage 2: Claim /dev/* devices under ROOT."""
        _logger.info("[BOOT 2/5] DEVICES: claiming /dev/* virtual hardware…")
        # Device registration is performed by AIOS.start() which has already
        # created and registered all devices with the DeviceManager before
        # calling boot().  Here we just verify ROOT owns them.
        if self._root.running:
            _logger.info("[BOOT 2/5] DEVICES: /dev/* claimed by ROOT")
        else:
            raise RuntimeError("ROOT must be running before devices can be claimed")

    def _stage_home_mount(self) -> None:
        """Stage 3: Mount HOME userland."""
        _logger.info("[BOOT 3/5] HOME: mounting userland layer…")
        self._home.start()
        self._root.mount_home(self._home)
        _logger.info("[BOOT 3/5] HOME: mounted")

    def _stage_aura_init(self) -> None:
        """Stage 4: Start all managed services via aura-init."""
        _logger.info("[BOOT 4/5] aura-init: starting system services…")
        self._aura_init.start_all()
        _logger.info("[BOOT 4/5] aura-init: all services started")

    def _stage_shell(self) -> None:
        """Stage 5: Shell is ready for operator input."""
        _logger.info("[BOOT 5/5] SHELL: operator shell ready")
        EVENT_BUS.publish("boot.shell_ready", {"ts": utcnow()})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_stage(self, stage: BootStage, fn: Callable) -> None:
        self._current_stage = stage
        rec = BootRecord(stage=stage, started_at=utcnow())
        t0 = time.monotonic()
        try:
            fn()
            rec.success = True
        except Exception as exc:
            rec.success = False
            rec.detail = str(exc)
            rec.duration_ms = (time.monotonic() - t0) * 1000.0
            rec.finished_at = utcnow()
            self._boot_log.append(rec)
            raise
        rec.duration_ms = (time.monotonic() - t0) * 1000.0
        rec.finished_at = utcnow()
        self._boot_log.append(rec)
        _logger.debug(
            "Boot stage %s: %.1f ms", stage.value, rec.duration_ms
        )

    def status(self) -> dict:
        elapsed = (time.monotonic() - self._boot_start) * 1000 if self._boot_start else 0
        return {
            "state": self._state.value,
            "current_stage": self._current_stage.value if self._current_stage else None,
            "elapsed_ms": round(elapsed, 2),
            "boot_log": self.boot_log,
        }
