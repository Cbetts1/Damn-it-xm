# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa DHCP Server
=================
Virtual DHCP server for the AURA network stack.

Manages IP lease assignment within a configurable subnet.  Leases have
a configurable TTL and are renewed on re-request.  The server does not
bind to a real UDP port — it operates as a virtual allocation table.
"""

from __future__ import annotations

import ipaddress
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.network.dhcp")


@dataclass
class DHCPLease:
    """A single DHCP IP lease."""
    ip: str
    mac: str          # client MAC or logical identifier
    hostname: str
    lease_start: float   # monotonic timestamp
    lease_time_s: int
    options: dict

    @property
    def expired(self) -> bool:
        return time.monotonic() > (self.lease_start + self.lease_time_s)

    @property
    def expires_in_s(self) -> float:
        remaining = (self.lease_start + self.lease_time_s) - time.monotonic()
        return max(0.0, remaining)

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "lease_time_s": self.lease_time_s,
            "expires_in_s": round(self.expires_in_s, 1),
            "expired": self.expired,
            "options": self.options,
        }


class DHCPServer:
    """
    Virtual DHCP server.

    Parameters
    ----------
    subnet:
        CIDR notation subnet string, e.g. ``"10.0.0.0/24"``.
    lease_time_s:
        Lease duration in seconds.
    """

    # Reserve the first 10 addresses for static assignments (gateway, DNS, etc.)
    _DYNAMIC_HOST_START = 11

    def __init__(
        self,
        subnet: str = "10.0.0.0/24",
        lease_time_s: int = 3600,
    ) -> None:
        self._net = ipaddress.IPv4Network(subnet, strict=False)
        self._lease_time = lease_time_s
        self._leases: Dict[str, DHCPLease] = {}   # mac → lease
        self._lock = threading.RLock()
        _logger.info("DHCP: subnet=%s lease_time=%ds", subnet, lease_time_s)

    # ------------------------------------------------------------------
    # Lease management
    # ------------------------------------------------------------------

    def request(self, mac: str, hostname: str = "", options: Optional[dict] = None) -> DHCPLease:
        """
        Request an IP lease for *mac*.

        If *mac* already has a valid lease, it is renewed.  Otherwise
        the next free IP in the pool is assigned.

        Raises
        ------
        RuntimeError
            If the address pool is exhausted.
        """
        with self._lock:
            # Renew existing lease
            existing = self._leases.get(mac)
            if existing and not existing.expired:
                existing.lease_start = time.monotonic()
                _logger.debug("DHCP renewed %s → %s", mac, existing.ip)
                return existing

            # Assign new IP
            ip = self._next_free_ip()
            if ip is None:
                raise RuntimeError("DHCP pool exhausted — no free addresses")
            lease = DHCPLease(
                ip=ip,
                mac=mac,
                hostname=hostname or mac,
                lease_start=time.monotonic(),
                lease_time_s=self._lease_time,
                options=options or {
                    "gateway": str(self._net.network_address + 1),
                    "dns": str(self._net.network_address + 2),
                    "subnet_mask": str(self._net.netmask),
                },
            )
            self._leases[mac] = lease
            _logger.info("DHCP assigned %s → %s (%s)", mac, ip, hostname)
            return lease

    def release(self, mac: str) -> bool:
        """Release the lease for *mac*.  Returns True if released."""
        with self._lock:
            if mac in self._leases:
                ip = self._leases[mac].ip
                del self._leases[mac]
                _logger.info("DHCP released %s (was %s)", mac, ip)
                return True
            return False

    def get_lease(self, mac: str) -> Optional[DHCPLease]:
        with self._lock:
            return self._leases.get(mac)

    def list_leases(self) -> List[dict]:
        with self._lock:
            self._evict_expired()
            return [l.to_dict() for l in self._leases.values()]

    def metrics(self) -> dict:
        with self._lock:
            self._evict_expired()
            hosts = list(self._net.hosts())
            pool_size = max(0, len(hosts) - self._DYNAMIC_HOST_START)
            return {
                "subnet": str(self._net),
                "pool_size": pool_size,
                "active_leases": len(self._leases),
                "free_addresses": pool_size - len(self._leases),
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evict_expired(self) -> None:
        expired = [mac for mac, l in self._leases.items() if l.expired]
        for mac in expired:
            _logger.debug("DHCP evicting expired lease for %s (%s)",
                          mac, self._leases[mac].ip)
            del self._leases[mac]

    def _next_free_ip(self) -> Optional[str]:
        assigned = {l.ip for l in self._leases.values()}
        hosts = list(self._net.hosts())
        for i, host in enumerate(hosts):
            if i < self._DYNAMIC_HOST_START:
                continue
            ip_str = str(host)
            if ip_str not in assigned:
                return ip_str
        return None
