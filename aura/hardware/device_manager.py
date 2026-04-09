# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa /dev/ Device Manager
==========================
The device manager is the registry for all virtual hardware devices.

ROOT claims every device at boot.  Userland processes open a device
through this registry, which enforces ROOT policy before granting access.

Devices are addressed by their /dev/ path:
  /dev/vcpu   — Virtual CPU
  /dev/vram   — Virtual RAM
  /dev/vdisk  — Virtual block storage
  /dev/vnet   — Virtual network (DHCP, DNS, NAT, firewall)
  /dev/vbt    — Virtual Bluetooth / bus transport
  /dev/vgpu   — Virtual GPU / compute dispatcher
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from aura.utils import get_logger, utcnow

if TYPE_CHECKING:
    from aura.root.sovereign import ROOTLayer

_logger = get_logger("aura.hardware.device_manager")


@dataclass
class DeviceDescriptor:
    """Metadata for a registered /dev/ device."""
    path: str          # e.g. "/dev/vcpu"
    kind: str          # e.g. "vcpu"
    device: Any        # the actual device object
    claimed_by: str    # identity that owns this device (usually "root")
    registered_at: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "kind": self.kind,
            "claimed_by": self.claimed_by,
            "registered_at": self.registered_at,
        }


class DeviceManager:
    """
    Registry and access controller for all /dev/ virtual devices.

    Parameters
    ----------
    root:
        Reference to the ROOT sovereign layer.  All open() calls are
        checked against ROOT policy before access is granted.
    """

    def __init__(self, root: "ROOTLayer") -> None:
        self._root = root
        self._devices: Dict[str, DeviceDescriptor] = {}
        self._lock = threading.RLock()
        _logger.info("DeviceManager initialised")

    # ------------------------------------------------------------------
    # Registration (ROOT-only)
    # ------------------------------------------------------------------

    def register(
        self,
        path: str,
        kind: str,
        device: Any,
        claimed_by: str = "root",
    ) -> DeviceDescriptor:
        """
        Register a device at *path*.

        Only ROOT or aura-init may register devices during boot.
        """
        with self._lock:
            if path in self._devices:
                raise ValueError(f"Device {path!r} already registered")
            desc = DeviceDescriptor(
                path=path,
                kind=kind,
                device=device,
                claimed_by=claimed_by,
                registered_at=utcnow(),
            )
            self._devices[path] = desc
            _logger.info("Device registered: %s (%s) claimed_by=%s",
                         path, kind, claimed_by)
            return desc

    # ------------------------------------------------------------------
    # Access (policy-gated)
    # ------------------------------------------------------------------

    def open(self, path: str, subject: str) -> Any:
        """
        Return the device at *path* after ROOT policy check.

        Parameters
        ----------
        path:
            /dev/ path of the device.
        subject:
            The identity requesting access (e.g. ``"root"``,
            ``"home"``, ``"build-pipeline"``).

        Returns
        -------
        Any
            The device object.

        Raises
        ------
        KeyError
            If the device is not registered.
        PermissionError
            If ROOT policy denies access.
        """
        with self._lock:
            if path not in self._devices:
                raise KeyError(f"Device not found: {path!r}")
            # ROOT gate check
            self._root.gate(
                subject=subject,
                action="device.open",
                resource=path,
                raise_on_deny=True,
            )
            device = self._devices[path].device
            _logger.debug("Device %s opened by %s", path, subject)
            return device

    def read(self, path: str, subject: str) -> Any:
        """Read device state/metrics (lighter policy check than open)."""
        with self._lock:
            if path not in self._devices:
                raise KeyError(f"Device not found: {path!r}")
            self._root.gate(
                subject=subject,
                action="device.read",
                resource=path,
                raise_on_deny=True,
            )
            return self._devices[path].device

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_devices(self) -> List[dict]:
        """Return a list of all registered device descriptors."""
        with self._lock:
            return [d.to_dict() for d in self._devices.values()]

    def get_descriptor(self, path: str) -> Optional[DeviceDescriptor]:
        with self._lock:
            return self._devices.get(path)

    def __contains__(self, path: str) -> bool:
        return path in self._devices
