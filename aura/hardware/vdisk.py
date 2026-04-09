# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa /dev/vdisk — Virtual Block Storage Device
================================================
Provides virtual block storage volumes for the AURA OS.

Each volume is a named, size-limited directory on the host filesystem.
The rootfs volume holds the SD-card-style system image.  HOME gets its
own writable overlay volume.  The build pipeline has a dedicated staging
volume.
"""

from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.hardware.vdisk")

DEV_PATH = "/dev/vdisk"


class VolumeStatus(str, Enum):
    AVAILABLE  = "available"
    MOUNTED    = "mounted"
    CREATING   = "creating"
    DELETING   = "deleting"


@dataclass
class DiskVolume:
    """A single virtual disk volume."""

    volume_id: str
    name: str
    size_gb: float
    status: VolumeStatus
    mount_point: Optional[str]     # filesystem path on host
    base_dir: str                  # root directory for this volume's data
    created_at: str
    mounted_by: Optional[str] = None

    @property
    def used_bytes(self) -> int:
        """Return approximate used bytes by walking the volume directory tree.

        Note: This performs a full directory walk and may be expensive for
        large volumes.  Call sparingly; prefer :meth:`VDiskDevice.metrics`
        for aggregate reporting.
        """
        if not self.mount_point or not os.path.isdir(self.mount_point):
            return 0
        total = 0
        try:
            for root, dirs, files in os.walk(self.mount_point):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    def to_dict(self) -> dict:
        used = self.used_bytes
        cap = int(self.size_gb * 1024 ** 3)
        return {
            "volume_id": self.volume_id,
            "name": self.name,
            "size_gb": self.size_gb,
            "status": self.status.value,
            "mount_point": self.mount_point,
            "used_bytes": used,
            "free_bytes": max(0, cap - used),
            "created_at": self.created_at,
            "mounted_by": self.mounted_by,
        }


class VDiskDevice:
    """
    /dev/vdisk — Virtual block storage device.

    Parameters
    ----------
    base_dir:
        Host filesystem directory under which volume data is stored.
    """

    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir
        self._volumes: Dict[str, DiskVolume] = {}
        self._lock = threading.RLock()
        os.makedirs(base_dir, exist_ok=True)
        _logger.info("/dev/vdisk: base_dir=%s", base_dir)

        # Provision the three system volumes automatically
        self._provision_system_volumes()

    @property
    def path(self) -> str:
        return DEV_PATH

    # ------------------------------------------------------------------
    # System volume provisioning
    # ------------------------------------------------------------------

    def _provision_system_volumes(self) -> None:
        """Provision the mandatory OS volumes if they don't exist."""
        system_vols = [
            ("rootfs",   64.0),   # SD-card rootfs
            ("home-vol",  8.0),   # HOME userland overlay
            ("stage-vol", 4.0),   # build pipeline staging
        ]
        for name, size_gb in system_vols:
            existing = next(
                (v for v in self._volumes.values() if v.name == name), None
            )
            if existing is None:
                self.create_volume(name, size_gb)

    # ------------------------------------------------------------------
    # Volume lifecycle
    # ------------------------------------------------------------------

    def create_volume(self, name: str, size_gb: float) -> dict:
        """Create a new volume.  Returns the volume dict."""
        with self._lock:
            vol_dir = os.path.join(self._base_dir, f"vol_{name}")
            os.makedirs(vol_dir, exist_ok=True)
            vol = DiskVolume(
                volume_id=generate_id("vol"),
                name=name,
                size_gb=size_gb,
                status=VolumeStatus.AVAILABLE,
                mount_point=None,
                base_dir=vol_dir,
                created_at=utcnow(),
            )
            self._volumes[vol.volume_id] = vol
            _logger.info("/dev/vdisk: created volume %s (%.1f GB)", name, size_gb)
            return vol.to_dict()

    def mount_volume(self, volume_id: str, mount_point: str, by: str = "root") -> bool:
        """Mount a volume at *mount_point*.  Returns True on success."""
        with self._lock:
            vol = self._volumes.get(volume_id)
            if vol is None:
                return False
            if vol.status == VolumeStatus.MOUNTED:
                return True  # already mounted
            os.makedirs(mount_point, exist_ok=True)
            vol.mount_point = mount_point
            vol.status = VolumeStatus.MOUNTED
            vol.mounted_by = by
            _logger.info("/dev/vdisk: volume %s mounted at %s by %s",
                         volume_id, mount_point, by)
            return True

    def unmount_volume(self, volume_id: str) -> bool:
        """Unmount a volume.  Returns True on success."""
        with self._lock:
            vol = self._volumes.get(volume_id)
            if vol is None or vol.status != VolumeStatus.MOUNTED:
                return False
            vol.mount_point = None
            vol.status = VolumeStatus.AVAILABLE
            vol.mounted_by = None
            _logger.info("/dev/vdisk: volume %s unmounted", volume_id)
            return True

    def delete_volume(self, volume_id: str) -> bool:
        """Delete a volume and its data.  Returns True on success."""
        with self._lock:
            vol = self._volumes.get(volume_id)
            if vol is None:
                return False
            if vol.status == VolumeStatus.MOUNTED:
                self.unmount_volume(volume_id)
            try:
                if os.path.isdir(vol.base_dir):
                    shutil.rmtree(vol.base_dir)
            except OSError as exc:
                _logger.warning("/dev/vdisk: delete error %s: %s", volume_id, exc)
            del self._volumes[volume_id]
            _logger.info("/dev/vdisk: volume %s deleted", volume_id)
            return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_volumes(self) -> List[dict]:
        with self._lock:
            return [v.to_dict() for v in self._volumes.values()]

    def get_volume(self, volume_id: str) -> Optional[dict]:
        with self._lock:
            v = self._volumes.get(volume_id)
            return v.to_dict() if v else None

    def get_volume_by_name(self, name: str) -> Optional[dict]:
        with self._lock:
            v = next((v for v in self._volumes.values() if v.name == name), None)
            return v.to_dict() if v else None

    def metrics(self) -> dict:
        with self._lock:
            vols = [v.to_dict() for v in self._volumes.values()]
            total_gb = sum(v["size_gb"] for v in vols)
            used_bytes = sum(v["used_bytes"] for v in vols)
            return {
                "device": DEV_PATH,
                "volume_count": len(vols),
                "total_gb": round(total_gb, 2),
                "used_bytes": used_bytes,
                "used_gb": round(used_bytes / 1024 ** 3, 3),
            }
