# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Filesystem Layer — Virtual File System (VFS)
==================================================
An in-memory, thread-safe virtual filesystem with mount-point support.
Nodes are stored as a nested dict tree; metadata is tracked per node.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.fs.vfs")

_TYPE_FILE = "file"
_TYPE_DIR  = "dir"


class VirtualFileSystem:
    """
    In-memory virtual filesystem.

    The tree is stored as nested dicts.  Each node has the structure::

        {
            "_meta": {
                "type":        "file" | "dir",
                "size":        int,          # bytes; 0 for dirs
                "created_at":  str,          # ISO-8601 UTC
                "modified_at": str,
            },
            "_data": bytes | None,           # only for file nodes
            # child names as additional keys (dir nodes only)
        }
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._root: dict = self._make_node(_TYPE_DIR)
        self._mounts: Dict[str, object] = {}
        _logger.info("VirtualFileSystem initialised")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_node(node_type: str, data: Optional[bytes] = None) -> dict:
        now = utcnow()
        return {
            "_meta": {
                "type":        node_type,
                "size":        len(data) if data is not None else 0,
                "created_at":  now,
                "modified_at": now,
            },
            "_data": data,
        }

    def _resolve(self, path: str) -> list:
        """
        Normalise *path* into a list of non-empty components.

        ``..`` traversal is silently stripped to prevent escaping the
        virtual root.
        """
        parts: list = []
        for part in path.replace("\\", "/").split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                # silently ignore upward traversal
                continue
            parts.append(part)
        return parts

    def _get_node(self, parts: list) -> Optional[dict]:
        """Walk the tree and return the node, or *None* if not found."""
        node = self._root
        for part in parts:
            child = node.get(part)
            if child is None:
                return None
            node = child
        return node

    def _get_parent(self, parts: list) -> Optional[dict]:
        """Return the parent node of the given path components."""
        return self._get_node(parts[:-1])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        """Return *True* if *path* exists in the VFS."""
        with self._lock:
            return self._get_node(self._resolve(path)) is not None

    def mkdir(self, path: str) -> bool:
        """
        Create a directory at *path*, creating any missing parents.

        Returns *True* on success, *False* if the path already exists as
        a file node.
        """
        parts = self._resolve(path)
        if not parts:
            return True  # root always exists
        with self._lock:
            node = self._root
            for part in parts:
                child = node.get(part)
                if child is None:
                    new_dir = self._make_node(_TYPE_DIR)
                    node[part] = new_dir
                    node = new_dir
                    _logger.debug("mkdir: created directory component '%s'", part)
                elif child["_meta"]["type"] == _TYPE_FILE:
                    _logger.warning("mkdir: '%s' already exists as a file", part)
                    return False
                else:
                    node = child
        _logger.info("mkdir: '%s' ready", path)
        return True

    def write(self, path: str, data: bytes) -> None:
        """Write *data* to a file node at *path*, creating parents as needed."""
        parts = self._resolve(path)
        if not parts:
            raise ValueError("Cannot write to the root node")
        with self._lock:
            # Ensure parent directories exist
            node = self._root
            for part in parts[:-1]:
                child = node.get(part)
                if child is None:
                    new_dir = self._make_node(_TYPE_DIR)
                    node[part] = new_dir
                    node = new_dir
                elif child["_meta"]["type"] == _TYPE_FILE:
                    raise ValueError(
                        f"Path component '{part}' is a file, not a directory"
                    )
                else:
                    node = child

            name = parts[-1]
            existing = node.get(name)
            if existing is not None and existing["_meta"]["type"] == _TYPE_DIR:
                raise ValueError(f"'{path}' is a directory, cannot write file")

            now = utcnow()
            if existing is None:
                node[name] = self._make_node(_TYPE_FILE, data)
            else:
                existing["_data"] = data
                existing["_meta"]["size"] = len(data)
                existing["_meta"]["modified_at"] = now
        _logger.debug("write: %d bytes written to '%s'", len(data), path)

    def read(self, path: str) -> Optional[bytes]:
        """Return the bytes stored at *path*, or *None* if not found/not a file."""
        parts = self._resolve(path)
        with self._lock:
            node = self._get_node(parts)
        if node is None or node["_meta"]["type"] != _TYPE_FILE:
            _logger.debug("read: '%s' not found or not a file", path)
            return None
        return node["_data"]

    def delete(self, path: str) -> bool:
        """
        Remove the node at *path*.

        Returns *True* on success, *False* if the path does not exist.
        """
        parts = self._resolve(path)
        if not parts:
            _logger.warning("delete: cannot delete the root node")
            return False
        with self._lock:
            parent = self._get_parent(parts)
            if parent is None or parts[-1] not in parent:
                _logger.debug("delete: '%s' not found", path)
                return False
            del parent[parts[-1]]
        _logger.info("delete: removed '%s'", path)
        return True

    def listdir(self, path: str) -> List[str]:
        """
        Return the names of entries inside the directory at *path*.

        Returns an empty list if the path does not exist or is not a directory.
        """
        parts = self._resolve(path)
        with self._lock:
            node = self._get_node(parts)
        if node is None or node["_meta"]["type"] != _TYPE_DIR:
            _logger.debug("listdir: '%s' not found or not a directory", path)
            return []
        return [k for k in node if not k.startswith("_")]

    def stat(self, path: str) -> Optional[dict]:
        """
        Return metadata for *path*, or *None* if not found.

        The returned dict contains: ``type``, ``size``, ``created_at``,
        ``modified_at``.
        """
        parts = self._resolve(path)
        with self._lock:
            node = self._get_node(parts)
        if node is None:
            return None
        return dict(node["_meta"])

    def mount(self, mount_point: str, fs_object: object) -> None:
        """Register *fs_object* as a virtual filesystem at *mount_point*."""
        with self._lock:
            self._mounts[mount_point] = fs_object
        _logger.info("mount: '%s' mounted", mount_point)

    def umount(self, mount_point: str) -> bool:
        """
        Unmount the filesystem at *mount_point*.

        Returns *True* on success, *False* if no mount exists at that point.
        """
        with self._lock:
            if mount_point not in self._mounts:
                _logger.warning("umount: '%s' is not mounted", mount_point)
                return False
            del self._mounts[mount_point]
        _logger.info("umount: '%s' unmounted", mount_point)
        return True
