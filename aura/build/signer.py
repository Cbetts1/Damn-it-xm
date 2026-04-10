# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Build — Artefact Signer
=============================
Signs and verifies build artefacts using HMAC-SHA256.
"""

from __future__ import annotations

import hashlib
import hmac


class ArtefactSigner:
    """
    Signs build artefacts with HMAC-SHA256.

    Parameters
    ----------
    signing_secret:
        The secret key used to generate and verify signatures.
    """

    def __init__(self, signing_secret: str) -> None:
        self._secret = signing_secret.encode()

    def sign(self, artefact_id: str, content_hash: str) -> str:
        """Return a 64-character hex HMAC-SHA256 signature for the artefact."""
        msg = f"{artefact_id}:{content_hash}".encode()
        return hmac.new(self._secret, msg, hashlib.sha256).hexdigest()

    def verify(self, artefact_id: str, content_hash: str, signature: str) -> bool:
        """Return True if *signature* matches the expected signature."""
        expected = self.sign(artefact_id, content_hash)
        return hmac.compare_digest(expected, signature)
