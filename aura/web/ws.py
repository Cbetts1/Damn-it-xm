# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Web — in-process WebSocket-style message hub."""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from aura.utils import get_logger, generate_id, utcnow


class WebSocketHub:
    """
    Pure in-process WebSocket-style message hub.

    No actual network sockets are used.  Clients connect by calling
    :meth:`connect`, which returns a ``client_id`` they use for all
    subsequent operations.
    """

    def __init__(self) -> None:
        self._clients: Dict[str, dict] = {}
        self._message_queue: Dict[str, List] = {}
        self._lock = threading.Lock()
        self._log = get_logger("aura.web.ws")

    def connect(self, client_id: Optional[str] = None) -> str:
        """Register a new client and return its ``client_id``."""
        cid = client_id or generate_id("ws-client")
        with self._lock:
            self._clients[cid] = {
                "client_id": cid,
                "subscriptions": [],
                "connected_at": utcnow(),
            }
            self._message_queue[cid] = []
        self._log.info("Client connected: %s", cid)
        return cid

    def disconnect(self, client_id: str) -> bool:
        with self._lock:
            if client_id not in self._clients:
                self._log.warning("Disconnect failed — unknown client: %s", client_id)
                return False
            del self._clients[client_id]
            self._message_queue.pop(client_id, None)
        self._log.info("Client disconnected: %s", client_id)
        return True

    def subscribe(self, client_id: str, topic: str) -> bool:
        with self._lock:
            if client_id not in self._clients:
                return False
            subs = self._clients[client_id]["subscriptions"]
            if topic not in subs:
                subs.append(topic)
        self._log.debug("Client %s subscribed to topic: %s", client_id, topic)
        return True

    def unsubscribe(self, client_id: str, topic: str) -> bool:
        with self._lock:
            if client_id not in self._clients:
                return False
            subs = self._clients[client_id]["subscriptions"]
            if topic in subs:
                subs.remove(topic)
        self._log.debug("Client %s unsubscribed from topic: %s", client_id, topic)
        return True

    def broadcast(self, topic: str, message: object) -> int:
        """Enqueue *message* for all clients subscribed to *topic*. Returns delivery count."""
        envelope = {"topic": topic, "message": message, "timestamp": utcnow()}
        count = 0
        with self._lock:
            for cid, client in self._clients.items():
                if topic in client["subscriptions"]:
                    self._message_queue[cid].append(envelope)
                    count += 1
        self._log.debug("Broadcast to topic %r delivered to %d client(s).", topic, count)
        return count

    def send(self, client_id: str, message: object) -> bool:
        """Enqueue *message* directly for *client_id*."""
        envelope = {"topic": None, "message": message, "timestamp": utcnow()}
        with self._lock:
            if client_id not in self._clients:
                self._log.warning("Send failed — unknown client: %s", client_id)
                return False
            self._message_queue[client_id].append(envelope)
        self._log.debug("Message sent to client: %s", client_id)
        return True

    def receive(self, client_id: str) -> List[dict]:
        """Return and clear all pending messages for *client_id*."""
        with self._lock:
            if client_id not in self._clients:
                return []
            messages = list(self._message_queue[client_id])
            self._message_queue[client_id] = []
        return messages

    def list_clients(self) -> List[dict]:
        with self._lock:
            return [
                {
                    "client_id": c["client_id"],
                    "subscriptions": list(c["subscriptions"]),
                    "connected_at": c["connected_at"],
                }
                for c in self._clients.values()
            ]
