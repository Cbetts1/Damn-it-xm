"""
AURa Persistence Engine
=======================
SQLite-backed key-value store with binary file management.

Provides:
  • Namespaced key-value storage (each namespace is a SQLite table)
  • Binary file storage under <data_dir>/cloud_storage/
  • Metrics reporting (namespace count, total keys, storage bytes)
"""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Dict, List, Optional

from aura.utils import get_logger, ensure_dir

_logger = get_logger("aura.persistence")


class PersistenceEngine:
    """
    SQLite-backed persistence engine for the AURa AI OS.

    All key-value data is stored in a single SQLite database with one table
    per namespace. Binary files are stored on the filesystem under the
    managed cloud_storage directory derived from the database location.
    """

    def __init__(self, db_path: str) -> None:
        """
        Open (or create) the SQLite database at *db_path*.

        The parent directory is created automatically if it does not exist.
        The managed file-storage root is placed at ``<parent>/cloud_storage/``.
        """
        self._db_path = db_path
        self._data_dir = os.path.dirname(os.path.abspath(db_path))
        self._storage_dir = os.path.join(self._data_dir, "cloud_storage")
        self._lock = threading.Lock()

        ensure_dir(self._data_dir)
        ensure_dir(self._storage_dir)

        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.commit()

        _logger.info("PersistenceEngine initialised: db=%s storage=%s", db_path, self._storage_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _table_name(self, namespace: str) -> str:
        """Sanitise namespace into a valid SQLite identifier."""
        safe = "".join(c if c.isalnum() or c == "_" else "_" for c in namespace)
        return f"ns_{safe}"

    def _ensure_namespace(self, namespace: str) -> None:
        """Create the namespace table if it does not yet exist."""
        tbl = self._table_name(namespace)
        with self._lock:
            self._conn.execute(
                f"CREATE TABLE IF NOT EXISTS {tbl} "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Key-Value API
    # ------------------------------------------------------------------

    def set(self, namespace: str, key: str, value: str) -> None:
        """Store *key* → *value* in *namespace*, overwriting any existing entry."""
        try:
            self._ensure_namespace(namespace)
            tbl = self._table_name(namespace)
            with self._lock:
                self._conn.execute(
                    f"INSERT OR REPLACE INTO {tbl} (key, value) VALUES (?, ?)",
                    (key, value),
                )
                self._conn.commit()
            _logger.debug("set [%s] %s", namespace, key)
        except Exception as exc:
            _logger.error("set error: %s", exc)
            raise

    def get(self, namespace: str, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve the value for *key* in *namespace*, or *default* if absent."""
        try:
            self._ensure_namespace(namespace)
            tbl = self._table_name(namespace)
            with self._lock:
                row = self._conn.execute(
                    f"SELECT value FROM {tbl} WHERE key = ?", (key,)
                ).fetchone()
            return row[0] if row else default
        except Exception as exc:
            _logger.error("get error: %s", exc)
            return default

    def delete(self, namespace: str, key: str) -> None:
        """Remove *key* from *namespace* (no-op if absent)."""
        try:
            self._ensure_namespace(namespace)
            tbl = self._table_name(namespace)
            with self._lock:
                self._conn.execute(f"DELETE FROM {tbl} WHERE key = ?", (key,))
                self._conn.commit()
            _logger.debug("delete [%s] %s", namespace, key)
        except Exception as exc:
            _logger.error("delete error: %s", exc)
            raise

    def list_keys(self, namespace: str) -> List[str]:
        """Return all keys stored in *namespace*."""
        try:
            self._ensure_namespace(namespace)
            tbl = self._table_name(namespace)
            with self._lock:
                rows = self._conn.execute(f"SELECT key FROM {tbl}").fetchall()
            return [r[0] for r in rows]
        except Exception as exc:
            _logger.error("list_keys error: %s", exc)
            return []

    def list_namespaces(self) -> List[str]:
        """Return all known namespace names."""
        try:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ns_%'"
                ).fetchall()
            # Strip the "ns_" prefix to recover the original namespace name
            return [r[0][3:] for r in rows]
        except Exception as exc:
            _logger.error("list_namespaces error: %s", exc)
            return []

    # ------------------------------------------------------------------
    # File Storage API
    # ------------------------------------------------------------------

    def save_file(self, path: str, data: bytes) -> str:
        """
        Save *data* under the managed storage root.

        *path* is treated as a relative path within ``cloud_storage/``.
        Returns the absolute path where the file was written.

        Raises ``ValueError`` if the resolved path would escape the storage root.
        """
        try:
            # Resolve to an absolute path and verify it stays within storage_dir
            if os.path.isabs(path):
                # Strip leading separator so it becomes relative
                path = os.path.relpath(path, "/")
            clean_path = os.path.normpath(path)
            if clean_path.startswith(".."):
                raise ValueError(f"Path '{path}' attempts to escape the storage root.")
            full_path = os.path.realpath(os.path.join(self._storage_dir, clean_path))
            storage_root = os.path.realpath(self._storage_dir)
            if not full_path.startswith(storage_root + os.sep) and full_path != storage_root:
                raise ValueError(f"Path '{path}' resolves outside the storage root.")
            ensure_dir(os.path.dirname(full_path))
            with open(full_path, "wb") as fh:
                fh.write(data)
            _logger.debug("save_file: %s (%d bytes)", full_path, len(data))
            return full_path
        except ValueError:
            raise
        except Exception as exc:
            _logger.error("save_file error: %s", exc)
            raise

    def load_file(self, path: str) -> bytes:
        """
        Load binary data from a path previously returned by :meth:`save_file`.

        Accepts either an absolute path or a relative path within cloud_storage.
        """
        try:
            if os.path.isabs(path):
                full_path = path
            else:
                clean_path = os.path.normpath(path).lstrip(os.sep)
                full_path = os.path.join(self._storage_dir, clean_path)
            with open(full_path, "rb") as fh:
                return fh.read()
        except Exception as exc:
            _logger.error("load_file error: %s", exc)
            raise

    def list_files(self, prefix: str = "") -> List[str]:
        """
        List all managed files whose relative path starts with *prefix*.

        Returns absolute paths.
        """
        results: List[str] = []
        try:
            for dirpath, _dirs, filenames in os.walk(self._storage_dir):
                for fname in filenames:
                    abs_path = os.path.join(dirpath, fname)
                    rel_path = os.path.relpath(abs_path, self._storage_dir)
                    if rel_path.startswith(prefix):
                        results.append(abs_path)
        except Exception as exc:
            _logger.error("list_files error: %s", exc)
        return results

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics(self) -> Dict[str, int]:
        """
        Return a summary dict with:
          • ``namespace_count`` — number of namespaces
          • ``total_keys``      — sum of all keys across all namespaces
          • ``storage_bytes``   — total bytes used by managed files
        """
        namespaces = self.list_namespaces()
        total_keys = sum(len(self.list_keys(ns)) for ns in namespaces)

        storage_bytes = 0
        try:
            for abs_path in self.list_files():
                try:
                    storage_bytes += os.path.getsize(abs_path)
                except OSError:
                    pass
        except Exception:
            pass

        return {
            "namespace_count": len(namespaces),
            "total_keys": total_keys,
            "storage_bytes": storage_bytes,
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        try:
            self._conn.close()
            _logger.debug("PersistenceEngine closed.")
        except Exception as exc:
            _logger.error("close error: %s", exc)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
