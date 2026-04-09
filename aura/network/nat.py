# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa NAT Table
===============
Virtual NAT (Network Address Translation) masquerade table for the
AURA network stack.

Tracks internal→external IP:port mappings and provides SNAT/DNAT
translation for outgoing and incoming traffic simulation.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.network.nat")


@dataclass
class NATEntry:
    """A single NAT translation entry."""
    entry_id: str
    internal_ip: str
    internal_port: int
    external_ip: str
    external_port: int
    protocol: str   # "tcp" or "udp"
    created_at: str
    packet_count: int = 0
    byte_count: int = 0

    @property
    def key(self) -> Tuple[str, int, str]:
        return (self.internal_ip, self.internal_port, self.protocol)

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "internal": f"{self.internal_ip}:{self.internal_port}/{self.protocol}",
            "external": f"{self.external_ip}:{self.external_port}/{self.protocol}",
            "packet_count": self.packet_count,
            "byte_count": self.byte_count,
            "created_at": self.created_at,
        }


class NATTable:
    """
    Virtual NAT masquerade table.

    In AURA, all outbound traffic from the virtual subnet is masqueraded
    through the gateway IP.  The table tracks the mapping so return
    traffic can be de-NATted back to the correct internal host.

    Parameters
    ----------
    gateway_ip:
        External (masquerade) IP address.
    internal_subnet:
        CIDR of the internal network (for informational purposes).
    """

    _EPHEMERAL_PORT_START = 32768
    _EPHEMERAL_PORT_END   = 60999

    def __init__(
        self,
        gateway_ip: str = "10.0.0.1",
        internal_subnet: str = "10.0.0.0/24",
    ) -> None:
        self._gateway_ip = gateway_ip
        self._internal_subnet = internal_subnet
        self._table: Dict[Tuple[str, int, str], NATEntry] = {}
        self._next_port = self._EPHEMERAL_PORT_START
        self._lock = threading.RLock()
        self._enabled = True
        _logger.info("NAT: gateway=%s subnet=%s", gateway_ip, internal_subnet)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        _logger.info("NAT: %s", "enabled" if value else "disabled")

    # ------------------------------------------------------------------
    # SNAT (outbound masquerade)
    # ------------------------------------------------------------------

    def snat(
        self,
        src_ip: str,
        src_port: int,
        dst_ip: str,
        dst_port: int,
        protocol: str = "tcp",
    ) -> Tuple[str, int]:
        """
        Apply SNAT to an outbound packet.

        Returns the (external_ip, external_port) to use as the source.
        If NAT is disabled, returns the original (src_ip, src_port).
        """
        if not self._enabled:
            return src_ip, src_port

        with self._lock:
            key = (src_ip, src_port, protocol)
            entry = self._table.get(key)
            if entry is None:
                ext_port = self._allocate_port()
                entry = NATEntry(
                    entry_id=generate_id("nat"),
                    internal_ip=src_ip,
                    internal_port=src_port,
                    external_ip=self._gateway_ip,
                    external_port=ext_port,
                    protocol=protocol,
                    created_at=utcnow(),
                )
                self._table[key] = entry
                _logger.debug(
                    "NAT SNAT: %s:%d/%s → %s:%d",
                    src_ip, src_port, protocol,
                    self._gateway_ip, ext_port,
                )
            entry.packet_count += 1
            return entry.external_ip, entry.external_port

    def dnat(
        self,
        dst_ip: str,
        dst_port: int,
        protocol: str = "tcp",
    ) -> Optional[Tuple[str, int]]:
        """
        Apply DNAT to an inbound packet.

        Returns the (internal_ip, internal_port) if a matching NAT entry
        exists, else ``None``.
        """
        with self._lock:
            for entry in self._table.values():
                if (entry.external_port == dst_port
                        and entry.protocol == protocol):
                    return entry.internal_ip, entry.internal_port
        return None

    def flush(self) -> int:
        """Remove all NAT entries.  Returns count removed."""
        with self._lock:
            count = len(self._table)
            self._table.clear()
            self._next_port = self._EPHEMERAL_PORT_START
            _logger.info("NAT table flushed (%d entries removed)", count)
            return count

    def list_entries(self) -> List[dict]:
        with self._lock:
            return [e.to_dict() for e in self._table.values()]

    def metrics(self) -> dict:
        with self._lock:
            total_pkts = sum(e.packet_count for e in self._table.values())
            return {
                "enabled": self._enabled,
                "gateway_ip": self._gateway_ip,
                "entry_count": len(self._table),
                "total_packets": total_pkts,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _allocate_port(self) -> int:
        port = self._next_port
        self._next_port += 1
        if self._next_port > self._EPHEMERAL_PORT_END:
            self._next_port = self._EPHEMERAL_PORT_START
        return port
