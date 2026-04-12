# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Virtual Network Node — in-process peer mesh bus."""

from __future__ import annotations

import threading
from typing import Dict, List

from aura.utils import get_logger, utcnow

_logger = get_logger("aura.vnode.mesh")


class MeshBus:
    """
    In-process pub/sub bus for virtual node-to-node communication.

    Peers register themselves by ``node_id``.  Messages are enqueued in
    per-peer inboxes and consumed via :meth:`receive`.
    """

    def __init__(self) -> None:
        self._peers: Dict[str, dict] = {}          # node_id → peer metadata
        self._inbox: Dict[str, List[dict]] = {}    # node_id → pending messages
        self._lock = threading.RLock()
        self._total_sent: int = 0
        _logger.info("MeshBus: initialised")

    # ------------------------------------------------------------------
    # Peer management
    # ------------------------------------------------------------------

    def register_peer(self, node_id: str, capabilities: List[str]) -> None:
        """Register (or refresh) a peer in the mesh."""
        with self._lock:
            self._peers[node_id] = {
                "node_id": node_id,
                "capabilities": list(capabilities),
                "registered_at": utcnow(),
            }
            if node_id not in self._inbox:
                self._inbox[node_id] = []
        _logger.info("MeshBus: peer registered: %s", node_id)

    def unregister_peer(self, node_id: str) -> bool:
        """Remove a peer from the mesh. Returns True if the peer was found."""
        with self._lock:
            if node_id not in self._peers:
                _logger.warning("MeshBus: unregister — unknown peer: %s", node_id)
                return False
            del self._peers[node_id]
            self._inbox.pop(node_id, None)
        _logger.info("MeshBus: peer unregistered: %s", node_id)
        return True

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def send_to_peer(self, node_id: str, message: dict) -> bool:
        """Enqueue *message* in the inbox of *node_id*. Returns False if unknown."""
        envelope = {"from": None, "message": message, "timestamp": utcnow()}
        with self._lock:
            if node_id not in self._peers:
                _logger.warning("MeshBus: send_to_peer — unknown peer: %s", node_id)
                return False
            self._inbox[node_id].append(envelope)
            self._total_sent += 1
        _logger.debug("MeshBus: message enqueued for peer: %s", node_id)
        return True

    def broadcast(self, topic: str, message: dict) -> int:
        """
        Deliver *message* to every registered peer.

        Returns the number of peers the message was delivered to.
        """
        envelope = {"topic": topic, "message": message, "timestamp": utcnow()}
        with self._lock:
            peer_ids = list(self._peers.keys())
            for pid in peer_ids:
                self._inbox[pid].append(envelope)
            self._total_sent += len(peer_ids)
        _logger.debug("MeshBus: broadcast topic=%r to %d peer(s).", topic, len(peer_ids))
        return len(peer_ids)

    def receive(self, node_id: str) -> List[dict]:
        """Return and clear all pending messages for *node_id*."""
        with self._lock:
            if node_id not in self._inbox:
                return []
            messages = list(self._inbox[node_id])
            self._inbox[node_id] = []
        return messages

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_peers(self) -> List[dict]:
        with self._lock:
            return [dict(p) for p in self._peers.values()]

    def metrics(self) -> dict:
        with self._lock:
            return {
                "peer_count": len(self._peers),
                "total_messages_sent": self._total_sent,
            }
