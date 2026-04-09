# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Persistence Engine
=======================
SQLite-backed storage for the AURa AI OS.

Features:
  • Namespaced key-value store (any JSON-serialisable value)
  • Binary blob / file storage with path-traversal protection
  • Thread-safe via SQLite WAL mode + a module-level threading.Lock
  • Zero required external dependencies (stdlib only)

Usage::

    engine = PersistenceEngine("/path/to/aura.db")
    engine.set("config", "theme", "dark")
    value = engine.get("config", "theme")   # → "dark"
    engine.store_file("blobs", "icon.png", b"<bytes>")
    data = engine.load_file("blobs", "icon.png")
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from typing import Any, Dict, Iterator, List, Optional

from aura.utils import get_logger

_logger = get_logger("aura.persistence")

# Allowed namespace / key pattern: letters, digits, underscore, hyphen, dot
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-\.]+$")


def _validate_name(name: str, label: str = "name") -> None:
    """Raise ValueError if *name* contains unsafe characters."""
    if not name or not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid {label} {name!r}: only letters, digits, '_', '-', '.' allowed"
        )


class PersistenceEngine:
    """
    SQLite-backed persistence engine for the AURa AI OS.

    All operations are thread-safe.  The database is created (with WAL
    journalling) the first time a ``PersistenceEngine`` is instantiated
    against a given path.

    Parameters
    ----------
    db_path:
        Absolute or relative path to the SQLite database file.
        Intermediate directories are created automatically.
    """

    # Maximum retries when the database is temporarily locked.
    _MAX_RETRIES: int = 3
    _RETRY_BASE_DELAY: float = 0.05  # 50 ms, doubled each retry

    def __init__(self, db_path: str) -> None:
        self._db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._lock = threading.Lock()
        self._conn = self._connect()
        self._init_schema()
        _logger.info("PersistenceEngine ready at %s", self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            timeout=10,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS kv_store (
                    namespace TEXT NOT NULL,
                    key       TEXT NOT NULL,
                    value     TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (namespace, key)
                );

                CREATE TABLE IF NOT EXISTS file_store (
                    namespace TEXT NOT NULL,
                    filename  TEXT NOT NULL,
                    data      BLOB NOT NULL,
                    size      INTEGER NOT NULL,
                    stored_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (namespace, filename)
                );
                """
            )

    def _exec_with_retry(self, fn):
        """Execute *fn(conn)* under the lock, retrying on ``OperationalError``
        (e.g. "database is locked") with exponential back-off.
        Returns whatever *fn* returns."""
        delay = self._RETRY_BASE_DELAY
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                with self._lock, self._conn:
                    return fn(self._conn)
            except sqlite3.OperationalError as exc:
                if attempt == self._MAX_RETRIES:
                    raise
                _logger.debug("SQLite retry %d/%d: %s", attempt, self._MAX_RETRIES, exc)
                time.sleep(delay)
                delay *= 2

    # ------------------------------------------------------------------
    # Key-value API
    # ------------------------------------------------------------------

    def set(self, namespace: str, key: str, value: Any) -> None:
        """Store *value* under (*namespace*, *key*).

        *value* must be JSON-serialisable.
        """
        _validate_name(namespace, "namespace")
        _validate_name(key, "key")
        serialised = json.dumps(value)

        def _op(conn):
            conn.execute(
                """
                INSERT INTO kv_store (namespace, key, value, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(namespace, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (namespace, key, serialised),
            )

        self._exec_with_retry(_op)

    def get(self, namespace: str, key: str, default: Any = None) -> Any:
        """Return the value stored at (*namespace*, *key*) or *default*."""
        _validate_name(namespace, "namespace")
        _validate_name(key, "key")
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM kv_store WHERE namespace=? AND key=?",
                (namespace, key),
            ).fetchone()
        if row is None:
            return default
        return json.loads(row[0])

    def delete(self, namespace: str, key: str) -> bool:
        """Delete the entry at (*namespace*, *key*). Returns True if deleted."""
        _validate_name(namespace, "namespace")
        _validate_name(key, "key")

        def _op(conn):
            cur = conn.execute(
                "DELETE FROM kv_store WHERE namespace=? AND key=?",
                (namespace, key),
            )
            return cur.rowcount > 0

        return self._exec_with_retry(_op)

    def list_keys(self, namespace: str) -> List[str]:
        """Return all keys in *namespace*."""
        _validate_name(namespace, "namespace")
        with self._lock:
            rows = self._conn.execute(
                "SELECT key FROM kv_store WHERE namespace=? ORDER BY key",
                (namespace,),
            ).fetchall()
        return [r[0] for r in rows]

    def all_items(self, namespace: str) -> Dict[str, Any]:
        """Return all key-value pairs in *namespace* as a dict."""
        _validate_name(namespace, "namespace")
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value FROM kv_store WHERE namespace=? ORDER BY key",
                (namespace,),
            ).fetchall()
        return {r[0]: json.loads(r[1]) for r in rows}

    def namespaces(self) -> List[str]:
        """Return a sorted list of all namespaces present in the KV store."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT namespace FROM kv_store ORDER BY namespace"
            ).fetchall()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Binary file / blob API
    # ------------------------------------------------------------------

    def store_file(self, namespace: str, filename: str, data: bytes) -> None:
        """Persist *data* as a named binary blob in *namespace*.

        Both *namespace* and *filename* are validated against a safe-name
        pattern to prevent path-traversal attacks.
        """
        _validate_name(namespace, "namespace")
        _validate_name(filename, "filename")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"data must be bytes, got {type(data).__name__}")

        def _op(conn):
            conn.execute(
                """
                INSERT INTO file_store (namespace, filename, data, size, stored_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(namespace, filename) DO UPDATE SET
                    data = excluded.data,
                    size = excluded.size,
                    stored_at = excluded.stored_at
                """,
                (namespace, filename, sqlite3.Binary(data), len(data)),
            )

        self._exec_with_retry(_op)

    def load_file(self, namespace: str, filename: str) -> Optional[bytes]:
        """Return the raw bytes stored under (*namespace*, *filename*), or None."""
        _validate_name(namespace, "namespace")
        _validate_name(filename, "filename")
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM file_store WHERE namespace=? AND filename=?",
                (namespace, filename),
            ).fetchone()
        return bytes(row[0]) if row else None

    def delete_file(self, namespace: str, filename: str) -> bool:
        """Delete a stored file. Returns True if the file existed."""
        _validate_name(namespace, "namespace")
        _validate_name(filename, "filename")

        def _op(conn):
            cur = conn.execute(
                "DELETE FROM file_store WHERE namespace=? AND filename=?",
                (namespace, filename),
            )
            return cur.rowcount > 0

        return self._exec_with_retry(_op)

    def list_files(self, namespace: str) -> List[Dict[str, Any]]:
        """List metadata for all stored files in *namespace*."""
        _validate_name(namespace, "namespace")
        with self._lock:
            rows = self._conn.execute(
                "SELECT filename, size, stored_at FROM file_store "
                "WHERE namespace=? ORDER BY filename",
                (namespace,),
            ).fetchall()
        return [{"filename": r[0], "size": r[1], "stored_at": r[2]} for r in rows]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with self._lock:
            self._conn.close()
        _logger.info("PersistenceEngine closed.")

    def __repr__(self) -> str:  # pragma: no cover
        return f"PersistenceEngine(db={self._db_path!r})"
