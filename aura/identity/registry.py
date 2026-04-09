# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Identity Registry
========================
Central registry for all AURA OS identity tokens.

The registry is ROOT-owned.  It stores all issued tokens and provides
lookup and revocation.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from aura.identity.crypto import IdentityToken, IdentityKind, CryptoIdentityEngine
from aura.utils import get_logger, utcnow

_logger = get_logger("aura.identity.registry")


class IdentityRegistry:
    """
    Registry for all AURA OS identity tokens.

    Parameters
    ----------
    engine:
        The :class:`CryptoIdentityEngine` used to issue and verify tokens.
    """

    def __init__(self, engine: CryptoIdentityEngine) -> None:
        self._engine = engine
        self._tokens: Dict[str, IdentityToken] = {}  # identity_id → token
        self._lock = threading.RLock()
        _logger.info("IdentityRegistry: initialised")

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------

    def issue(
        self,
        kind: IdentityKind,
        subject: str,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> IdentityToken:
        """Issue and store a new identity token."""
        token = self._engine.issue(kind, subject, ttl_seconds, metadata)
        with self._lock:
            self._tokens[token.identity_id] = token
        _logger.info(
            "IdentityRegistry: issued %s for %s (%s)",
            token.identity_id, subject, kind.value,
        )
        return token

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, identity_id: str) -> Optional[IdentityToken]:
        with self._lock:
            return self._tokens.get(identity_id)

    def find_by_subject(self, subject: str) -> List[IdentityToken]:
        with self._lock:
            return [t for t in self._tokens.values() if t.subject == subject]

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify(self, identity_id: str) -> bool:
        """Return True if the token is valid (not revoked, not expired, sig OK)."""
        with self._lock:
            token = self._tokens.get(identity_id)
            if token is None:
                return False
        return self._engine.verify(token)

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------

    def revoke(self, identity_id: str) -> bool:
        """Revoke a token.  Returns True if the token was found."""
        with self._lock:
            token = self._tokens.get(identity_id)
            if token is None:
                return False
            token.revoked = True
        _logger.warning("IdentityRegistry: revoked %s", identity_id)
        return True

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_tokens(self, kind: Optional[IdentityKind] = None) -> List[dict]:
        with self._lock:
            tokens = list(self._tokens.values())
        if kind:
            tokens = [t for t in tokens if t.kind == kind]
        return [t.to_dict() for t in tokens]

    def metrics(self) -> dict:
        with self._lock:
            total = len(self._tokens)
            revoked = sum(1 for t in self._tokens.values() if t.revoked)
            expired = sum(1 for t in self._tokens.values() if t.expired)
        return {
            "total_tokens": total,
            "revoked": revoked,
            "expired": expired,
            "active": total - revoked - expired,
        }
