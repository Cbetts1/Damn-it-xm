# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa ROOT — Approval Gate
==========================
The ROOT Approval Gate is the mandatory gatekeeper that every build artefact
must pass before it is promoted to production.

Workflow
--------
1. Build pipeline calls ``ApprovalGate.request(artefact_id, submitter, metadata)``.
2. Gate records the request with status PENDING and returns an
   :class:`ApprovalRequest` object.
3. ROOT (or an authorised ADMIN) calls ``ApprovalGate.approve(request_id)``
   or ``ApprovalGate.reject(request_id, reason)``.
4. Build pipeline checks ``ApprovalRequest.status`` before deploying.

No artefact may be deployed while its request is PENDING or REJECTED.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.root.approval")


class ApprovalStatus(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED  = "expired"


@dataclass
class ApprovalRequest:
    """A single ROOT approval request for a build artefact."""

    request_id: str
    artefact_id: str
    submitter: str
    status: ApprovalStatus
    metadata: dict
    created_at: str
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    reject_reason: Optional[str] = None
    # HMAC token issued on approval, verified by the deploy step
    deploy_token: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "artefact_id": self.artefact_id,
            "submitter": self.submitter,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "reject_reason": self.reject_reason,
            "has_deploy_token": self.deploy_token is not None,
        }


class ApprovalGate:
    """
    ROOT Approval Gate.

    Parameters
    ----------
    signing_secret:
        HMAC-SHA256 secret used to sign deploy tokens.  Must be kept
        confidential and owned by ROOT.
    ttl_seconds:
        How long a PENDING request lives before it auto-expires (default
        24 hours).  0 = never expire.
    max_pending:
        Maximum number of simultaneous PENDING requests.
    auto_approve:
        If ``True``, immediately approve every incoming request (CI mode).
        Should never be ``True`` in production.
    """

    def __init__(
        self,
        signing_secret: str,
        ttl_seconds: int = 86400,
        max_pending: int = 64,
        auto_approve: bool = False,
    ) -> None:
        self._secret = signing_secret.encode()
        self._ttl = ttl_seconds
        self._max_pending = max_pending
        self._auto_approve = auto_approve
        self._requests: Dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()
        _logger.info(
            "ApprovalGate online (auto_approve=%s, ttl=%ds)",
            auto_approve, ttl_seconds,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request(
        self,
        artefact_id: str,
        submitter: str,
        metadata: Optional[dict] = None,
    ) -> ApprovalRequest:
        """
        Submit an approval request for *artefact_id*.

        Returns the :class:`ApprovalRequest`.  If ``auto_approve`` is
        enabled the request is immediately approved and a deploy token
        is generated.

        Raises
        ------
        RuntimeError
            If the pending queue is full.
        """
        with self._lock:
            pending_count = sum(
                1 for r in self._requests.values()
                if r.status == ApprovalStatus.PENDING
            )
            if pending_count >= self._max_pending:
                raise RuntimeError(
                    f"Approval gate full: {pending_count} pending requests"
                )

            req = ApprovalRequest(
                request_id=generate_id("approval"),
                artefact_id=artefact_id,
                submitter=submitter,
                status=ApprovalStatus.PENDING,
                metadata=metadata or {},
                created_at=utcnow(),
            )
            self._requests[req.request_id] = req
            _logger.info(
                "Approval requested: %s for artefact %s by %s",
                req.request_id, artefact_id, submitter,
            )

            if self._auto_approve:
                self._do_approve(req, decided_by="auto")

            return req

    def approve(self, request_id: str, decided_by: str = "root") -> ApprovalRequest:
        """Approve the request with *request_id*.

        Returns the updated :class:`ApprovalRequest` with a deploy token.

        Raises
        ------
        KeyError
            If the request does not exist.
        ValueError
            If the request is not in PENDING status.
        """
        with self._lock:
            req = self._get_or_raise(request_id)
            if req.status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Cannot approve request {request_id!r}: status={req.status.value}"
                )
            self._do_approve(req, decided_by=decided_by)
            return req

    def reject(
        self,
        request_id: str,
        reason: str = "Rejected by ROOT",
        decided_by: str = "root",
    ) -> ApprovalRequest:
        """Reject the request with *request_id*.

        Returns the updated :class:`ApprovalRequest`.
        """
        with self._lock:
            req = self._get_or_raise(request_id)
            if req.status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Cannot reject request {request_id!r}: status={req.status.value}"
                )
            req.status = ApprovalStatus.REJECTED
            req.decided_at = utcnow()
            req.decided_by = decided_by
            req.reject_reason = reason
            _logger.warning(
                "Approval rejected: %s (artefact=%s) reason=%r",
                request_id, req.artefact_id, reason,
            )
            return req

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        """Return the request, or ``None`` if not found."""
        with self._lock:
            req = self._requests.get(request_id)
            if req is not None:
                self._maybe_expire(req)
            return req

    def list_requests(
        self, status: Optional[ApprovalStatus] = None
    ) -> List[dict]:
        """Return all requests, optionally filtered by *status*."""
        with self._lock:
            for req in list(self._requests.values()):
                self._maybe_expire(req)
            results = [
                r.to_dict() for r in self._requests.values()
                if status is None or r.status == status
            ]
        return sorted(results, key=lambda x: x["created_at"], reverse=True)

    def verify_deploy_token(self, artefact_id: str, token: str) -> bool:
        """Return True if *token* is a valid ROOT-issued deploy token for *artefact_id*."""
        expected = self._make_token(artefact_id)
        return hmac.compare_digest(token.encode(), expected.encode())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _do_approve(self, req: ApprovalRequest, decided_by: str) -> None:
        req.status = ApprovalStatus.APPROVED
        req.decided_at = utcnow()
        req.decided_by = decided_by
        req.deploy_token = self._make_token(req.artefact_id)
        _logger.info(
            "Approval granted: %s (artefact=%s) by=%s",
            req.request_id, req.artefact_id, decided_by,
        )

    def _make_token(self, artefact_id: str) -> str:
        """Generate an HMAC-SHA256 deploy token for *artefact_id*."""
        return hmac.new(
            self._secret,
            artefact_id.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _get_or_raise(self, request_id: str) -> ApprovalRequest:
        req = self._requests.get(request_id)
        if req is None:
            raise KeyError(f"Approval request not found: {request_id!r}")
        return req

    def _maybe_expire(self, req: ApprovalRequest) -> None:
        if self._ttl <= 0 or req.status != ApprovalStatus.PENDING:
            return
        # Parse ISO timestamp manually to avoid datetime import
        try:
            # created_at is "YYYY-MM-DDTHH:MM:SS.ffffffZ"
            # Use time.time() comparison via monotonic approximation
            from datetime import datetime, timezone
            created = datetime.fromisoformat(req.created_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age = (now - created).total_seconds()
            if age > self._ttl:
                req.status = ApprovalStatus.EXPIRED
                _logger.warning(
                    "Approval expired: %s (artefact=%s)",
                    req.request_id, req.artefact_id,
                )
        except Exception:
            pass
