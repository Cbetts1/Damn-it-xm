# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Kernel — Secrets Manager
==============================
Thread-safe in-memory store for named secrets.  Keys are validated to
contain only alphanumeric characters and underscores.  Values are never
logged or returned via :meth:`list_keys`.
"""

from __future__ import annotations

import re
import threading
from typing import Dict, List, Optional

from aura.utils import get_logger

_logger = get_logger("aura.kernel.secrets")

_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_key(key: str) -> None:
    """Raise ``ValueError`` if *key* contains invalid characters."""
    if not key:
        raise ValueError("Secret key must not be empty")
    if not _KEY_RE.match(key):
        raise ValueError(
            f"Invalid secret key {key!r}: only alphanumeric characters and "
            "underscores are permitted"
        )


class SecretsManager:
    """
    In-memory secrets store with key validation and rotation support.

    All mutations are protected by a ``threading.Lock``.  Secret values
    are never emitted to logs.
    """

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}
        self._lock = threading.Lock()
        _logger.info("SecretsManager initialised")

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def set_secret(self, key: str, value: str) -> None:
        """
        Store or overwrite a secret.

        Parameters
        ----------
        key:
            Alphanumeric + underscore identifier.
        value:
            Secret value (not logged).

        Raises
        ------
        ValueError
            If *key* contains invalid characters.
        """
        _validate_key(key)
        with self._lock:
            self._store[key] = value
        _logger.info("Secret set: key=%s", key)

    def delete_secret(self, key: str) -> bool:
        """
        Remove a secret.

        Returns
        -------
        bool
            ``True`` if the key existed, ``False`` otherwise.
        """
        _validate_key(key)
        with self._lock:
            existed = key in self._store
            self._store.pop(key, None)
        if existed:
            _logger.info("Secret deleted: key=%s", key)
        else:
            _logger.warning("delete_secret: key=%s not found", key)
        return existed

    def rotate_secret(self, key: str, new_value: str) -> bool:
        """
        Update an *existing* secret's value.

        Unlike :meth:`set_secret`, this method refuses to create a new
        key — it only updates a key that already exists.

        Returns
        -------
        bool
            ``True`` if the key existed and was updated, ``False`` if
            the key was not found.
        """
        _validate_key(key)
        with self._lock:
            if key not in self._store:
                _logger.warning("rotate_secret: key=%s not found", key)
                return False
            self._store[key] = new_value
        _logger.info("Secret rotated: key=%s", key)
        return True

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_secret(self, key: str) -> Optional[str]:
        """Return the secret value for *key*, or ``None`` if absent."""
        _validate_key(key)
        with self._lock:
            return self._store.get(key)

    def list_keys(self) -> List[str]:
        """Return all stored key names (values are never exposed)."""
        with self._lock:
            return sorted(self._store.keys())
