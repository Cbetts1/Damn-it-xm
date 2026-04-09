# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa ROOT — Sovereign Layer
============================
ROOT is the highest-privilege layer of the AURA OS.  It:

  • Owns all /dev/* virtual devices (claimed at boot; released only at halt).
  • Hosts the policy engine (all-deny by default).
  • Hosts the approval gate (mandatory pre-deploy checkpoint).
  • Mounts and unmounts the HOME userland.
  • Maintains the audit log (every privileged action is recorded).
  • Is the root of cryptographic trust (signs identity tokens, deploy tokens).

Nothing outside this module may claim ROOT privileges — they must call
:meth:`ROOTLayer.gate` and receive an explicit ALLOW verdict.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from aura.config import AURaConfig, ROOTConfig
from aura.root.policy import PolicyEngine, PolicyRule, PolicyVerdict
from aura.root.approval import ApprovalGate, ApprovalRequest, ApprovalStatus
from aura.utils import get_logger, utcnow, EVENT_BUS

if TYPE_CHECKING:
    from aura.hardware.device_manager import DeviceManager

_logger = get_logger("aura.root")


# ---------------------------------------------------------------------------
# Audit log entry
# ---------------------------------------------------------------------------

class AuditEntry:
    """A single ROOT audit log entry."""

    __slots__ = ("ts", "subject", "action", "resource", "verdict", "detail")

    def __init__(
        self,
        subject: str,
        action: str,
        resource: str,
        verdict: str,
        detail: str = "",
    ) -> None:
        self.ts = utcnow()
        self.subject = subject
        self.action = action
        self.resource = resource
        self.verdict = verdict
        self.detail = detail

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "subject": self.subject,
            "action": self.action,
            "resource": self.resource,
            "verdict": self.verdict,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# ROOTLayer
# ---------------------------------------------------------------------------

class ROOTLayer:
    """
    The AURA ROOT sovereign layer.

    Only one ROOTLayer instance should exist per system.  It is
    instantiated before any other component and shut down last.

    Parameters
    ----------
    config:
        Full system configuration.  ROOT reads its own settings from
        ``config.root``.
    """

    def __init__(self, config: AURaConfig) -> None:
        self._config = config
        self._root_cfg: ROOTConfig = config.root
        self._lock = threading.RLock()
        self._running = False
        self._start_time: Optional[float] = None

        # Policy and approval subsystems
        self._policy: PolicyEngine = PolicyEngine.with_os_defaults()
        self._approval_gate: ApprovalGate = ApprovalGate(
            signing_secret=self._root_cfg.root_secret,
            max_pending=self._root_cfg.max_pending_approvals,
            auto_approve=config.build.auto_approve_ci,
        )

        # Audit log (in-memory, bounded)
        self._audit: List[AuditEntry] = []
        self._audit_max = self._root_cfg.audit_log_max_entries

        # HOME mount state
        self._home_mounted = False

        # Device manager reference (set during boot by AIOS)
        self._device_manager: Optional["DeviceManager"] = None

        _logger.info("ROOT layer created")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def policy(self) -> PolicyEngine:
        """The ROOT policy engine."""
        return self._policy

    @property
    def approval_gate(self) -> ApprovalGate:
        """The ROOT deployment approval gate."""
        return self._approval_gate

    @property
    def running(self) -> bool:
        return self._running

    @property
    def home_mounted(self) -> bool:
        return self._home_mounted

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Bring ROOT online.  Called first in the boot sequence."""
        if self._running:
            return
        _logger.info("ROOT layer starting…")
        self._start_time = time.monotonic()
        self._running = True
        self._audit_write("root", "root.start", "system", "allow",
                          "ROOT layer online")
        EVENT_BUS.publish("root.started", {"ts": utcnow()})
        _logger.info("ROOT layer ONLINE (policy=deny-by-default)")

    def stop(self) -> None:
        """Bring ROOT offline.  Called last in the shutdown sequence."""
        if not self._running:
            return
        _logger.info("ROOT layer stopping…")
        if self._home_mounted:
            self.unmount_home()
        self._running = False
        self._audit_write("root", "root.stop", "system", "allow",
                          "ROOT layer halted")
        EVENT_BUS.publish("root.stopped", {"ts": utcnow()})
        _logger.info("ROOT layer OFFLINE")

    # ------------------------------------------------------------------
    # HOME mount/unmount
    # ------------------------------------------------------------------

    def mount_home(self, home_layer: Any) -> None:
        """
        Mount the HOME userland layer.

        Called by the boot chain after ROOT is online.  HOME is allowed
        restricted access to /dev/* resources through ROOT-gated
        interfaces.
        """
        with self._lock:
            if self._home_mounted:
                _logger.warning("HOME already mounted — ignoring duplicate mount")
                return
            self._gate("root", "home.mount", "home", raise_on_deny=True)
            self._home_mounted = True
            self._audit_write("root", "home.mount", "home", "allow",
                              "HOME userland mounted")
            EVENT_BUS.publish("root.home.mounted", {"ts": utcnow()})
            _logger.info("HOME userland mounted")

    def unmount_home(self) -> None:
        """Unmount the HOME userland layer."""
        with self._lock:
            if not self._home_mounted:
                return
            self._home_mounted = False
            self._audit_write("root", "home.unmount", "home", "allow",
                              "HOME userland unmounted")
            EVENT_BUS.publish("root.home.unmounted", {"ts": utcnow()})
            _logger.info("HOME userland unmounted")

    # ------------------------------------------------------------------
    # Device manager binding
    # ------------------------------------------------------------------

    def bind_device_manager(self, dm: "DeviceManager") -> None:
        """Bind the /dev/ device manager.  Called during boot."""
        self._device_manager = dm
        _logger.info("ROOT: /dev/ device manager bound")

    # ------------------------------------------------------------------
    # Policy gate — public API
    # ------------------------------------------------------------------

    def gate(
        self,
        subject: str,
        action: str,
        resource: str,
        raise_on_deny: bool = False,
    ) -> PolicyVerdict:
        """
        Evaluate the ROOT policy for (subject, action, resource).

        Every privileged operation should call this before proceeding.
        If *raise_on_deny* is True, raises :class:`PermissionError` on
        DENY verdicts.  AUDIT verdicts are written to the audit log and
        returned as ALLOW.

        Returns
        -------
        PolicyVerdict
            The verdict (ALLOW / DENY / AUDIT).
        """
        verdict = self._policy.evaluate(subject, action, resource)
        self._audit_write(subject, action, resource, verdict.value)

        if verdict == PolicyVerdict.AUDIT:
            _logger.info("ROOT AUDIT: %s %s %s", subject, action, resource)

        if verdict == PolicyVerdict.DENY and raise_on_deny:
            raise PermissionError(
                f"ROOT denied: subject={subject!r} action={action!r} "
                f"resource={resource!r}"
            )
        return verdict

    def _gate(
        self,
        subject: str,
        action: str,
        resource: str,
        raise_on_deny: bool = False,
    ) -> PolicyVerdict:
        """Internal gate call — does not write a separate audit entry."""
        return self._policy.evaluate(subject, action, resource)

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def _audit_write(
        self,
        subject: str,
        action: str,
        resource: str,
        verdict: str,
        detail: str = "",
    ) -> None:
        with self._lock:
            entry = AuditEntry(subject, action, resource, verdict, detail)
            self._audit.append(entry)
            # Evict oldest entries when over capacity
            if len(self._audit) > self._audit_max:
                self._audit = self._audit[-(self._audit_max):]

    def audit_log(self, last_n: int = 100) -> List[dict]:
        """Return the last *last_n* audit log entries (newest last)."""
        with self._lock:
            return [e.to_dict() for e in self._audit[-last_n:]]

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> dict:
        uptime = (time.monotonic() - self._start_time) if self._start_time else 0
        return {
            "running": self._running,
            "home_mounted": self._home_mounted,
            "uptime_seconds": round(uptime, 1),
            "policy_rules": len(self._policy.list_rules()),
            "audit_entries": len(self._audit),
            "pending_approvals": len(
                self._approval_gate.list_requests(ApprovalStatus.PENDING)
            ),
        }
