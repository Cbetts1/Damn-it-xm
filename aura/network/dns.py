# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa DNS Resolver
==================
Virtual DNS resolver for the AURA network stack.

Supports:
  • Static A/CNAME records (aura.local zone)
  • Override / intercept of any name resolution
  • Upstream forwarding fallback (configurable)
  • PTR records for reverse lookups within the virtual subnet
"""

from __future__ import annotations

import re
import socket
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.network.dns")


@dataclass
class DNSRecord:
    """A virtual DNS record."""
    name: str           # fully-qualified domain name
    rtype: str          # "A", "CNAME", "PTR", "TXT"
    value: str          # the record data
    ttl: int = 300
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "rtype": self.rtype,
            "value": self.value,
            "ttl": self.ttl,
            "created_at": self.created_at,
        }


class DNSResolver:
    """
    Virtual DNS resolver.

    Parameters
    ----------
    upstream:
        Upstream DNS server IP for forwarding unresolved names.
    search_domain:
        Local search domain appended to short names.
    """

    def __init__(
        self,
        upstream: str = "8.8.8.8",
        search_domain: str = "aura.local",
    ) -> None:
        self._upstream = upstream
        self._search_domain = search_domain
        self._records: Dict[str, List[DNSRecord]] = {}
        self._lock = threading.RLock()

        # Seed well-known local records
        self._seed_defaults()
        _logger.info("DNS: upstream=%s search_domain=%s", upstream, search_domain)

    # ------------------------------------------------------------------
    # Record management
    # ------------------------------------------------------------------

    def add_record(self, record: DNSRecord) -> None:
        """Add a DNS record.  Multiple records for the same name are allowed."""
        with self._lock:
            key = record.name.lower().rstrip(".")
            self._records.setdefault(key, []).append(record)
            _logger.debug("DNS add: %s %s → %s", record.name, record.rtype, record.value)

    def remove_record(self, name: str, rtype: Optional[str] = None) -> int:
        """Remove records for *name* (optionally filtering by *rtype*).  Returns count."""
        with self._lock:
            key = name.lower().rstrip(".")
            existing = self._records.get(key, [])
            if rtype:
                kept = [r for r in existing if r.rtype.upper() != rtype.upper()]
                removed = len(existing) - len(kept)
                self._records[key] = kept
            else:
                removed = len(existing)
                self._records.pop(key, None)
            return removed

    def override(self, name: str, ip: str, ttl: int = 300) -> None:
        """
        Override (intercept) *name* to resolve to *ip*.

        Replaces any existing A record for *name*.
        """
        with self._lock:
            key = name.lower().rstrip(".")
            self._records[key] = [
                DNSRecord(name=name, rtype="A", value=ip, ttl=ttl)
            ]
            _logger.info("DNS override: %s → %s", name, ip)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, name: str, rtype: str = "A") -> Optional[str]:
        """
        Resolve *name* to a value.

        Checks local records first; falls back to upstream if not found.

        Returns
        -------
        str or None
            The resolved value, or ``None`` if unresolvable.
        """
        name = name.lower().rstrip(".")

        with self._lock:
            # Direct match
            records = self._records.get(name, [])
            matching = [r for r in records if r.rtype.upper() == rtype.upper()]
            if matching:
                return matching[0].value

            # Try with search domain
            fqdn = f"{name}.{self._search_domain}"
            records = self._records.get(fqdn, [])
            matching = [r for r in records if r.rtype.upper() == rtype.upper()]
            if matching:
                return matching[0].value

        # Forward to upstream
        return self._upstream_resolve(name, rtype)

    def _upstream_resolve(self, name: str, rtype: str) -> Optional[str]:
        if rtype != "A":
            return None
        try:
            result = socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)
            if result:
                ip = result[0][4][0]
                _logger.debug("DNS upstream: %s → %s", name, ip)
                return ip
        except (socket.gaierror, OSError):
            pass
        return None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_records(self) -> List[dict]:
        with self._lock:
            out = []
            for records in self._records.values():
                out.extend(r.to_dict() for r in records)
            return out

    def metrics(self) -> dict:
        with self._lock:
            total = sum(len(v) for v in self._records.values())
            return {
                "zone_count": len(self._records),
                "record_count": total,
                "upstream": self._upstream,
                "search_domain": self._search_domain,
            }

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    def _seed_defaults(self) -> None:
        defaults = [
            DNSRecord("aura.local",           "A",   "10.0.0.1"),
            DNSRecord("gateway.aura.local",   "A",   "10.0.0.1"),
            DNSRecord("dns.aura.local",       "A",   "10.0.0.2"),
            DNSRecord("api.aura.local",       "A",   "127.0.0.1"),
            DNSRecord("dashboard.aura.local", "A",   "127.0.0.1"),
            DNSRecord("root.aura.local",      "A",   "10.0.0.1"),
            DNSRecord("home.aura.local",      "A",   "10.0.0.10"),
        ]
        for rec in defaults:
            self.add_record(rec)
