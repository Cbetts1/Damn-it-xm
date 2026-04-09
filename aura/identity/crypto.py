# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Cryptographic Identity
============================
Every node, user, plugin, and artefact in the AURA OS has a
cryptographic identity.  ROOT is the root of trust — it issues and
validates all identity tokens.

Identity tokens are HMAC-SHA256 signed to prevent forgery.  Each
identity has:
  • A unique ID (UUID-based)
  • A type (node / user / plugin / artefact)
  • A public fingerprint (SHA-256 of the identity payload)
  • An HMAC signature from ROOT
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.identity.crypto")


class IdentityKind(str, Enum):
    NODE      = "node"
    USER      = "user"
    PLUGIN    = "plugin"
    ARTEFACT  = "artefact"
    SERVICE   = "service"


@dataclass
class IdentityToken:
    """A ROOT-issued cryptographic identity token."""

    identity_id: str
    kind: IdentityKind
    subject: str          # the entity being identified (name or ID)
    fingerprint: str      # SHA-256 of the canonical payload
    signature: str        # HMAC-SHA256 ROOT signature
    issued_at: str
    expires_at: Optional[str] = None
    revoked: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "kind": self.kind.value,
            "subject": self.subject,
            "fingerprint": self.fingerprint,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "revoked": self.revoked,
            "metadata": self.metadata,
        }

    @property
    def expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            from datetime import datetime, timezone
            exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except Exception:
            return False


class CryptoIdentityEngine:
    """
    ROOT-owned cryptographic identity engine.

    Issues and verifies :class:`IdentityToken` objects.  Uses
    HMAC-SHA256 with the ROOT secret as the signing key.

    Parameters
    ----------
    root_secret:
        The ROOT signing secret.  Must be kept confidential.
    """

    def __init__(self, root_secret: str) -> None:
        self._secret = root_secret.encode()
        _logger.info("CryptoIdentityEngine: initialised")

    # ------------------------------------------------------------------
    # Token issuance
    # ------------------------------------------------------------------

    def issue(
        self,
        kind: IdentityKind,
        subject: str,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> IdentityToken:
        """
        Issue a new identity token for *subject*.

        Parameters
        ----------
        kind:
            The type of entity being identified.
        subject:
            The entity name or ID.
        ttl_seconds:
            If set, the token expires after this many seconds.
        metadata:
            Additional metadata to embed in the token.

        Returns
        -------
        IdentityToken
        """
        issued_at = utcnow()
        expires_at = None
        if ttl_seconds:
            from datetime import datetime, timezone, timedelta
            exp_dt = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            expires_at = exp_dt.isoformat().replace("+00:00", "Z")

        payload = self._canonical_payload(kind, subject, issued_at, metadata or {})
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        signature = hmac.new(
            self._secret, payload.encode(), hashlib.sha256
        ).hexdigest()

        token = IdentityToken(
            identity_id=generate_id("id"),
            kind=kind,
            subject=subject,
            fingerprint=fingerprint,
            signature=signature,
            issued_at=issued_at,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        _logger.debug(
            "Identity issued: %s kind=%s subject=%s",
            token.identity_id, kind.value, subject,
        )
        return token

    # ------------------------------------------------------------------
    # Token verification
    # ------------------------------------------------------------------

    def verify(self, token: IdentityToken) -> bool:
        """
        Verify the token's HMAC signature.

        Returns True if the signature is valid, the token is not
        revoked, and it has not expired.
        """
        if token.revoked:
            return False
        if token.expired:
            return False
        payload = self._canonical_payload(
            token.kind, token.subject, token.issued_at, token.metadata
        )
        expected = hmac.new(
            self._secret, payload.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, token.signature)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _canonical_payload(
        kind: IdentityKind,
        subject: str,
        issued_at: str,
        metadata: dict,
    ) -> str:
        """Produce a deterministic canonical string for signing."""
        return json.dumps(
            {"kind": kind.value, "subject": subject, "issued_at": issued_at,
             "metadata": metadata},
            sort_keys=True,
            separators=(",", ":"),
        )
