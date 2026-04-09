# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa /dev/vbt — Virtual Bluetooth / Bus Transport
===================================================
Virtual Bluetooth and generic bus transport device.

Manages virtual peripheral pairing, service advertisement, and bus
message routing.  In real hardware this would map to the BT adapter;
in the AURA virtual layer it provides a message bus that any subsystem
can use for out-of-band signalling.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow, EVENT_BUS

_logger = get_logger("aura.hardware.vbt")

DEV_PATH = "/dev/vbt"


class PeripheralState(str, Enum):
    DISCOVERED = "discovered"
    PAIRING    = "pairing"
    PAIRED     = "paired"
    CONNECTED  = "connected"
    DISCONNECTED = "disconnected"


@dataclass
class VirtualPeripheral:
    """A virtual Bluetooth/bus peripheral."""
    device_id: str
    name: str
    address: str        # BT MAC address or virtual bus address
    service: str        # advertised service UUID or name
    state: PeripheralState
    paired_at: Optional[str] = None
    connected_at: Optional[str] = None
    rssi: int = -60     # simulated signal strength (dBm)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "address": self.address,
            "service": self.service,
            "state": self.state.value,
            "paired_at": self.paired_at,
            "connected_at": self.connected_at,
            "rssi": self.rssi,
        }


class VBTDevice:
    """
    /dev/vbt — Virtual Bluetooth / Bus Transport device.

    Provides:
    • Peripheral discovery and pairing
    • Bus message routing (publish/subscribe on top of EventBus)
    • Service advertisement
    """

    def __init__(self) -> None:
        self._peripherals: Dict[str, VirtualPeripheral] = {}
        self._lock = threading.RLock()
        self._power_on = True
        _logger.info("/dev/vbt: device ready")

    @property
    def path(self) -> str:
        return DEV_PATH

    # ------------------------------------------------------------------
    # Power management
    # ------------------------------------------------------------------

    def power_on(self) -> None:
        self._power_on = True
        _logger.info("/dev/vbt: powered ON")

    def power_off(self) -> None:
        self._power_on = False
        _logger.info("/dev/vbt: powered OFF")

    # ------------------------------------------------------------------
    # Peripheral management
    # ------------------------------------------------------------------

    def discover(self, name: str, address: str, service: str = "generic") -> VirtualPeripheral:
        """Register a newly discovered peripheral."""
        with self._lock:
            dev_id = generate_id("bt")
            p = VirtualPeripheral(
                device_id=dev_id,
                name=name,
                address=address,
                service=service,
                state=PeripheralState.DISCOVERED,
            )
            self._peripherals[dev_id] = p
            _logger.info("/dev/vbt: discovered %s (%s)", name, address)
            EVENT_BUS.publish("vbt.discovered", p.to_dict())
            return p

    def pair(self, device_id: str) -> bool:
        """Pair with a discovered peripheral.  Returns True on success."""
        with self._lock:
            p = self._peripherals.get(device_id)
            if p is None:
                return False
            p.state = PeripheralState.PAIRED
            p.paired_at = utcnow()
            _logger.info("/dev/vbt: paired with %s (%s)", p.name, p.address)
            EVENT_BUS.publish("vbt.paired", p.to_dict())
            return True

    def connect(self, device_id: str) -> bool:
        """Connect to a paired peripheral.  Returns True on success."""
        with self._lock:
            p = self._peripherals.get(device_id)
            if p is None or p.state not in (PeripheralState.PAIRED,
                                             PeripheralState.DISCONNECTED):
                return False
            p.state = PeripheralState.CONNECTED
            p.connected_at = utcnow()
            _logger.info("/dev/vbt: connected to %s", p.name)
            EVENT_BUS.publish("vbt.connected", p.to_dict())
            return True

    def disconnect(self, device_id: str) -> bool:
        """Disconnect from a connected peripheral."""
        with self._lock:
            p = self._peripherals.get(device_id)
            if p is None or p.state != PeripheralState.CONNECTED:
                return False
            p.state = PeripheralState.DISCONNECTED
            _logger.info("/dev/vbt: disconnected from %s", p.name)
            EVENT_BUS.publish("vbt.disconnected", {"device_id": device_id})
            return True

    def list_peripherals(self) -> List[dict]:
        with self._lock:
            return [p.to_dict() for p in self._peripherals.values()]

    # ------------------------------------------------------------------
    # Bus message routing
    # ------------------------------------------------------------------

    def send(self, device_id: str, payload: dict) -> bool:
        """Send a payload to a connected peripheral (via EventBus)."""
        with self._lock:
            p = self._peripherals.get(device_id)
            if p is None or p.state != PeripheralState.CONNECTED:
                return False
        EVENT_BUS.publish(f"vbt.message.{device_id}", payload)
        return True

    def subscribe(self, device_id: str, callback: Callable) -> None:
        """Subscribe to messages from a peripheral."""
        EVENT_BUS.subscribe(f"vbt.message.{device_id}", callback)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics(self) -> dict:
        with self._lock:
            connected = sum(
                1 for p in self._peripherals.values()
                if p.state == PeripheralState.CONNECTED
            )
            return {
                "device": DEV_PATH,
                "power_on": self._power_on,
                "peripheral_count": len(self._peripherals),
                "connected_count": connected,
            }
