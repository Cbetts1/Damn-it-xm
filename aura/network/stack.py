# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Network Stack — /dev/vnet
================================
Unified virtual network stack exposed as the /dev/vnet device.

Composes:
  • DHCP server      — IP lease management
  • DNS resolver     — name resolution with override/intercept
  • NAT table        — masquerade (SNAT/DNAT)
  • Firewall         — stateful packet filter (all-deny by default)
"""

from __future__ import annotations

import threading
from typing import List, Optional

from aura.config import NetworkConfig
from aura.network.dhcp import DHCPServer, DHCPLease
from aura.network.dns import DNSResolver, DNSRecord
from aura.network.nat import NATTable
from aura.network.firewall import Firewall, FirewallRule, FirewallVerdict
from aura.utils import get_logger

_logger = get_logger("aura.network.stack")

DEV_PATH = "/dev/vnet"


class NetworkStack:
    """
    /dev/vnet — unified virtual network stack.

    All four subsystems (DHCP, DNS, NAT, firewall) are co-owned by ROOT
    via this single device interface.

    Parameters
    ----------
    config:
        NetworkConfig from the system configuration.
    """

    def __init__(self, config: NetworkConfig) -> None:
        self._config = config
        self._lock = threading.RLock()

        self.dhcp = DHCPServer(
            subnet=config.dhcp_subnet,
            lease_time_s=config.dhcp_lease_time_s,
        )
        self.dns = DNSResolver(
            upstream=config.dns_upstream,
            search_domain=config.dns_search_domain,
        )
        self.nat = NATTable(
            gateway_ip=self._gateway_ip(),
            internal_subnet=config.dhcp_subnet,
        )
        self.nat.enabled = config.nat_enabled

        self.firewall = Firewall.with_os_defaults()

        # Apply extra rules from config
        for rule_str in config.firewall_allow_rules:
            self._apply_config_rule(rule_str)

        _logger.info(
            "/dev/vnet: DHCP=%s DNS=%s NAT=%s FW=deny-by-default",
            config.dhcp_subnet, config.dns_upstream, config.nat_enabled,
        )

    @property
    def path(self) -> str:
        return DEV_PATH

    # ------------------------------------------------------------------
    # DHCP passthrough
    # ------------------------------------------------------------------

    def dhcp_request(self, mac: str, hostname: str = "") -> DHCPLease:
        """Request an IP lease.  Wrapper around DHCPServer.request()."""
        return self.dhcp.request(mac, hostname)

    def dhcp_release(self, mac: str) -> bool:
        return self.dhcp.release(mac)

    def dhcp_list(self) -> List[dict]:
        return self.dhcp.list_leases()

    # ------------------------------------------------------------------
    # DNS passthrough
    # ------------------------------------------------------------------

    def dns_resolve(self, name: str, rtype: str = "A") -> Optional[str]:
        return self.dns.resolve(name, rtype)

    def dns_override(self, name: str, ip: str) -> None:
        self.dns.override(name, ip)
        _logger.info("DNS override: %s → %s", name, ip)

    def dns_add(self, name: str, rtype: str, value: str, ttl: int = 300) -> None:
        self.dns.add_record(DNSRecord(name=name, rtype=rtype, value=value, ttl=ttl))

    # ------------------------------------------------------------------
    # NAT passthrough
    # ------------------------------------------------------------------

    def nat_snat(self, src_ip: str, src_port: int, dst_ip: str, dst_port: int,
                 protocol: str = "tcp"):
        """Apply SNAT to an outbound packet via /dev/vnet.  Returns (external_ip, external_port).

        See :meth:`aura.network.nat.NATTable.snat` for full documentation.
        """
        return self.nat.snat(src_ip, src_port, dst_ip, dst_port, protocol)

    # ------------------------------------------------------------------
    # Firewall passthrough
    # ------------------------------------------------------------------

    def fw_allow(self, src_ip: str, dst_ip: str, protocol: str, dst_port: int,
                 direction: str = "out") -> bool:
        return self.firewall.allow(src_ip, dst_ip, protocol, dst_port, direction)

    def fw_add_rule(self, rule: FirewallRule) -> None:
        self.firewall.add_rule(rule)

    def fw_remove_rule(self, name: str) -> bool:
        return self.firewall.remove_rule(name)

    def fw_list_rules(self) -> List[dict]:
        return self.firewall.list_rules()

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics(self) -> dict:
        return {
            "device": DEV_PATH,
            "dhcp": self.dhcp.metrics(),
            "dns": self.dns.metrics(),
            "nat": self.nat.metrics(),
            "firewall": self.firewall.metrics(),
        }

    def status(self) -> str:
        return "online"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _gateway_ip(self) -> str:
        """Derive gateway IP from subnet (first usable host)."""
        try:
            import ipaddress
            net = ipaddress.IPv4Network(self._config.dhcp_subnet, strict=False)
            return str(list(net.hosts())[0])
        except Exception:
            return "10.0.0.1"

    def _apply_config_rule(self, rule_str: str) -> None:
        """
        Apply a config-file rule string like ``"tcp:8000"`` as a firewall
        ALLOW rule.
        """
        try:
            proto, port_str = rule_str.split(":", 1)
            port = int(port_str)
            self.fw_add_rule(FirewallRule(
                name=f"config-allow-{proto}-{port}",
                src_ip="*",
                dst_ip="*",
                protocol=proto,
                dst_port=port,
                verdict=FirewallVerdict.ALLOW,
                priority=50,
                direction="both",
            ))
        except (ValueError, TypeError) as exc:
            _logger.warning("NetworkStack: invalid config rule %r: %s", rule_str, exc)
