# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Firewall
==============
Stateful firewall for the AURA network stack.

All-deny by default.  ROOT must explicitly add ALLOW rules before any
traffic is permitted.  Rules are evaluated in priority order (lower
number = higher priority).  The first matching rule wins.

Rule matching:
  • src/dst IP supports CIDR notation (``"10.0.0.0/24"``) or exact IP
    (``"10.0.0.5"``) or wildcard (``"*"``).
  • protocol: ``"tcp"``, ``"udp"``, ``"icmp"``, or ``"*"``.
  • port: integer, ``"*"``, or ``"0"`` (any).
"""

from __future__ import annotations

import ipaddress
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.network.firewall")


class FirewallVerdict(str, Enum):
    ALLOW = "allow"
    DENY  = "deny"
    DROP  = "drop"    # drop silently (no RST)
    LOG   = "log"     # allow and log


@dataclass
class FirewallRule:
    """A single stateful firewall rule."""

    name: str
    src_ip: str           # "10.0.0.0/24" | "10.0.0.5" | "*"
    dst_ip: str
    protocol: str         # "tcp" | "udp" | "icmp" | "*"
    dst_port: int         # 0 = any
    verdict: FirewallVerdict
    priority: int = 100
    direction: str = "both"  # "in" | "out" | "both"
    created_at: str = field(default_factory=utcnow)
    hit_count: int = 0

    def matches(
        self,
        src_ip: str,
        dst_ip: str,
        protocol: str,
        dst_port: int,
        direction: str = "out",
    ) -> bool:
        if self.direction not in (direction, "both"):
            return False
        if not self._ip_matches(src_ip, self.src_ip):
            return False
        if not self._ip_matches(dst_ip, self.dst_ip):
            return False
        if self.protocol not in ("*", protocol.lower()):
            return False
        if self.dst_port != 0 and self.dst_port != dst_port:
            return False
        return True

    @staticmethod
    def _ip_matches(ip: str, pattern: str) -> bool:
        if pattern == "*":
            return True
        try:
            if "/" in pattern:
                return ipaddress.ip_address(ip) in ipaddress.ip_network(pattern, strict=False)
            return ip == pattern
        except ValueError:
            return False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "protocol": self.protocol,
            "dst_port": self.dst_port,
            "verdict": self.verdict.value,
            "priority": self.priority,
            "direction": self.direction,
            "hit_count": self.hit_count,
            "created_at": self.created_at,
        }


class Firewall:
    """
    Stateful firewall for the AURA network stack.

    Default policy: DENY.  ROOT adds explicit ALLOW rules.

    Parameters
    ----------
    default_verdict:
        Policy when no rule matches.
    """

    def __init__(
        self,
        default_verdict: FirewallVerdict = FirewallVerdict.DENY,
    ) -> None:
        self._default = default_verdict
        self._rules: List[FirewallRule] = []
        self._lock = threading.RLock()
        self._enabled = True
        _logger.info("Firewall: default=%s", default_verdict.value)

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: FirewallRule) -> None:
        """Add a firewall rule (kept sorted by priority)."""
        with self._lock:
            self._rules.append(rule)
            self._rules.sort(key=lambda r: r.priority)
            _logger.debug("Firewall rule added: %s (priority=%d verdict=%s)",
                          rule.name, rule.priority, rule.verdict.value)

    def remove_rule(self, name: str) -> bool:
        """Remove rule by name.  Returns True if removed."""
        with self._lock:
            before = len(self._rules)
            self._rules = [r for r in self._rules if r.name != name]
            return len(self._rules) < before

    def flush(self) -> int:
        """Remove all rules.  Returns count removed."""
        with self._lock:
            count = len(self._rules)
            self._rules.clear()
            return count

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False
        _logger.warning("Firewall DISABLED — all traffic permitted")

    # ------------------------------------------------------------------
    # Packet evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        src_ip: str,
        dst_ip: str,
        protocol: str,
        dst_port: int,
        direction: str = "out",
    ) -> FirewallVerdict:
        """
        Evaluate a packet against the firewall rules.

        Returns
        -------
        FirewallVerdict
            The matching verdict, or the default if no rule matches.
        """
        if not self._enabled:
            return FirewallVerdict.ALLOW

        with self._lock:
            for rule in self._rules:
                if rule.matches(src_ip, dst_ip, protocol, dst_port, direction):
                    rule.hit_count += 1
                    _logger.debug(
                        "FW %s: %s → %s/%s:%d verdict=%s rule=%s",
                        direction, src_ip, dst_ip, protocol, dst_port,
                        rule.verdict.value, rule.name,
                    )
                    return rule.verdict
        return self._default

    def allow(
        self,
        src_ip: str,
        dst_ip: str,
        protocol: str,
        dst_port: int,
        direction: str = "out",
    ) -> bool:
        """Return True if this packet is allowed."""
        v = self.evaluate(src_ip, dst_ip, protocol, dst_port, direction)
        return v in (FirewallVerdict.ALLOW, FirewallVerdict.LOG)

    # ------------------------------------------------------------------
    # Bootstrap defaults
    # ------------------------------------------------------------------

    @classmethod
    def with_os_defaults(cls) -> "Firewall":
        """Return a firewall pre-loaded with AURA OS default rules."""
        fw = cls(default_verdict=FirewallVerdict.DENY)

        # Allow loopback
        fw.add_rule(FirewallRule(
            name="allow-loopback",
            src_ip="127.0.0.0/8",
            dst_ip="*",
            protocol="*",
            dst_port=0,
            verdict=FirewallVerdict.ALLOW,
            priority=1,
            direction="both",
        ))

        # Allow internal virtual subnet
        fw.add_rule(FirewallRule(
            name="allow-internal-subnet",
            src_ip="10.0.0.0/24",
            dst_ip="10.0.0.0/24",
            protocol="*",
            dst_port=0,
            verdict=FirewallVerdict.ALLOW,
            priority=5,
            direction="both",
        ))

        # Allow established API port (8000)
        fw.add_rule(FirewallRule(
            name="allow-api-8000",
            src_ip="*",
            dst_ip="*",
            protocol="tcp",
            dst_port=8000,
            verdict=FirewallVerdict.ALLOW,
            priority=10,
            direction="both",
        ))

        # Allow SSH
        fw.add_rule(FirewallRule(
            name="allow-ssh",
            src_ip="*",
            dst_ip="*",
            protocol="tcp",
            dst_port=22,
            verdict=FirewallVerdict.ALLOW,
            priority=11,
            direction="both",
        ))

        # Allow HTTP/HTTPS outbound
        for port, pname in [(80, "http"), (443, "https")]:
            fw.add_rule(FirewallRule(
                name=f"allow-{pname}-out",
                src_ip="10.0.0.0/24",
                dst_ip="*",
                protocol="tcp",
                dst_port=port,
                verdict=FirewallVerdict.ALLOW,
                priority=20,
                direction="out",
            ))

        # Allow DNS (UDP 53)
        fw.add_rule(FirewallRule(
            name="allow-dns-udp",
            src_ip="*",
            dst_ip="*",
            protocol="udp",
            dst_port=53,
            verdict=FirewallVerdict.ALLOW,
            priority=15,
            direction="both",
        ))

        return fw

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_rules(self) -> List[dict]:
        with self._lock:
            return [r.to_dict() for r in self._rules]

    def metrics(self) -> dict:
        with self._lock:
            total_hits = sum(r.hit_count for r in self._rules)
            return {
                "enabled": self._enabled,
                "default_verdict": self._default.value,
                "rule_count": len(self._rules),
                "total_hits": total_hits,
            }
