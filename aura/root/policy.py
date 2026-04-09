# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa ROOT — Policy Engine
==========================
Implements the ROOT all-deny-by-default policy gate.

Every privileged action (device access, deploy, network rule change, etc.) must
pass through the PolicyEngine before it is executed.  The engine evaluates a
priority-ordered list of :class:`PolicyRule` objects and returns a
:class:`PolicyVerdict`.

Rules are matched on (subject, action, resource) triples.  The first matching
rule wins.  If no rule matches, the default policy (from :class:`ROOTConfig`)
is applied — normally ``"deny"``.
"""

from __future__ import annotations

import fnmatch
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.root.policy")


class PolicyVerdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"  # allow but write to audit log


@dataclass
class PolicyRule:
    """
    A single ROOT policy rule.

    Matching uses shell-style glob patterns (``*`` = any, ``?`` = one char).

    Attributes
    ----------
    name:
        Human-readable rule name for audit output.
    subject:
        Who is making the request.  Glob pattern matched against
        ``subject`` argument of :meth:`PolicyEngine.evaluate`.
    action:
        What they want to do (e.g. ``"read"``, ``"write"``, ``"deploy"``,
        ``"device.open"``).  Glob pattern.
    resource:
        What resource they're acting on (e.g. ``"/dev/vnet"``,
        ``"artefact:*"``).  Glob pattern.
    verdict:
        The :class:`PolicyVerdict` to return when this rule matches.
    priority:
        Lower numbers are evaluated first.  Default ``100``.
    """

    name: str
    subject: str
    action: str
    resource: str
    verdict: PolicyVerdict
    priority: int = 100
    created_at: str = field(default_factory=utcnow)

    def matches(self, subject: str, action: str, resource: str) -> bool:
        return (
            fnmatch.fnmatch(subject, self.subject)
            and fnmatch.fnmatch(action, self.action)
            and fnmatch.fnmatch(resource, self.resource)
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "subject": self.subject,
            "action": self.action,
            "resource": self.resource,
            "verdict": self.verdict.value,
            "priority": self.priority,
            "created_at": self.created_at,
        }


class PolicyEngine:
    """
    ROOT policy engine — evaluates rules in priority order.

    The engine is thread-safe.  Rules can be added and removed at runtime
    by ROOT-authorised callers only.

    Parameters
    ----------
    default_verdict:
        The verdict to return if no rule matches.  Should be
        :attr:`PolicyVerdict.DENY` in production.
    """

    def __init__(self, default_verdict: PolicyVerdict = PolicyVerdict.DENY) -> None:
        self._default = default_verdict
        self._rules: List[PolicyRule] = []
        self._lock = threading.RLock()
        _logger.info("PolicyEngine initialised (default=%s)", default_verdict.value)

    # ------------------------------------------------------------------
    # Rule management
    # ------------------------------------------------------------------

    def add_rule(self, rule: PolicyRule) -> None:
        """Add a policy rule.  Rules are kept sorted by priority."""
        with self._lock:
            self._rules.append(rule)
            self._rules.sort(key=lambda r: r.priority)
            _logger.debug("Rule added: %s (priority=%d verdict=%s)",
                          rule.name, rule.priority, rule.verdict.value)

    def remove_rule(self, name: str) -> bool:
        """Remove the rule with *name*.  Returns True if removed."""
        with self._lock:
            before = len(self._rules)
            self._rules = [r for r in self._rules if r.name != name]
            removed = len(self._rules) < before
            if removed:
                _logger.debug("Rule removed: %s", name)
            return removed

    def list_rules(self) -> List[dict]:
        """Return all rules as a list of dicts."""
        with self._lock:
            return [r.to_dict() for r in self._rules]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        subject: str,
        action: str,
        resource: str,
    ) -> PolicyVerdict:
        """
        Evaluate a (subject, action, resource) request.

        Returns the first matching :class:`PolicyVerdict`, or the default
        verdict if no rule matches.
        """
        with self._lock:
            for rule in self._rules:
                if rule.matches(subject, action, resource):
                    _logger.debug(
                        "Policy: %s %s %s → %s (rule=%s)",
                        subject, action, resource,
                        rule.verdict.value, rule.name,
                    )
                    return rule.verdict
        _logger.debug(
            "Policy: %s %s %s → %s (default)",
            subject, action, resource, self._default.value,
        )
        return self._default

    def require(self, subject: str, action: str, resource: str) -> None:
        """
        Raise :class:`PermissionError` if the verdict is DENY.

        AUDIT verdicts are allowed through (they are logged by the caller).
        """
        verdict = self.evaluate(subject, action, resource)
        if verdict == PolicyVerdict.DENY:
            raise PermissionError(
                f"ROOT policy denied: subject={subject!r} "
                f"action={action!r} resource={resource!r}"
            )

    # ------------------------------------------------------------------
    # Convenience: bootstrap safe defaults
    # ------------------------------------------------------------------

    @classmethod
    def with_os_defaults(cls) -> "PolicyEngine":
        """
        Return a PolicyEngine pre-loaded with AURA OS default rules.

        These are the minimum rules required for the OS to function:
        - ROOT identity may do anything.
        - aura-init may open any /dev/ device.
        - HOME processes may read (but not write) /dev/ devices.
        - Build pipeline artefact signing is ROOT-only.
        - Network rule changes are ROOT-only.
        """
        engine = cls(default_verdict=PolicyVerdict.DENY)

        # ROOT is all-powerful
        engine.add_rule(PolicyRule(
            name="root-superuser",
            subject="root",
            action="*",
            resource="*",
            verdict=PolicyVerdict.ALLOW,
            priority=1,
        ))

        # aura-init can open /dev/* during boot
        engine.add_rule(PolicyRule(
            name="init-device-open",
            subject="aura-init",
            action="device.open",
            resource="/dev/*",
            verdict=PolicyVerdict.ALLOW,
            priority=5,
        ))

        # HOME processes may READ any /dev/ device (audited)
        engine.add_rule(PolicyRule(
            name="home-device-read",
            subject="home",
            action="device.read",
            resource="/dev/*",
            verdict=PolicyVerdict.AUDIT,
            priority=10,
        ))

        # Build pipeline may submit artefacts for staging
        engine.add_rule(PolicyRule(
            name="build-artefact-stage",
            subject="build-pipeline",
            action="artefact.stage",
            resource="artefact:*",
            verdict=PolicyVerdict.ALLOW,
            priority=20,
        ))

        # Only ROOT may sign and deploy artefacts
        engine.add_rule(PolicyRule(
            name="root-artefact-deploy",
            subject="root",
            action="artefact.deploy",
            resource="artefact:*",
            verdict=PolicyVerdict.ALLOW,
            priority=2,
        ))

        # ADMIN users may read system status
        engine.add_rule(PolicyRule(
            name="admin-status-read",
            subject="admin",
            action="read",
            resource="system:*",
            verdict=PolicyVerdict.ALLOW,
            priority=30,
        ))

        # OPERATOR users may read and write (but not deploy)
        engine.add_rule(PolicyRule(
            name="operator-read-write",
            subject="operator",
            action="read",
            resource="*",
            verdict=PolicyVerdict.ALLOW,
            priority=40,
        ))
        engine.add_rule(PolicyRule(
            name="operator-write",
            subject="operator",
            action="write",
            resource="*",
            verdict=PolicyVerdict.ALLOW,
            priority=41,
        ))

        # Regular users may only read
        engine.add_rule(PolicyRule(
            name="user-read",
            subject="user",
            action="read",
            resource="*",
            verdict=PolicyVerdict.ALLOW,
            priority=50,
        ))

        return engine
