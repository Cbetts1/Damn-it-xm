# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""
AURa Kernel — Inter-Process Communication Bus
==============================================
Named message channels backed by ``queue.Queue``.  Producers call
``send``; consumers call ``receive``.  All operations are thread-safe
by virtue of ``queue.Queue``'s own locking.
"""

from __future__ import annotations

import queue
from typing import Any, Dict, List, Optional

from aura.utils import get_logger

_logger = get_logger("aura.kernel.ipc")


class IPCBus:
    """
    Lightweight named-channel message bus.

    Each channel is a ``queue.Queue`` created on first use.  Channels
    are never automatically removed; use :meth:`clear` to drain one.
    """

    def __init__(self) -> None:
        self._channels: Dict[str, queue.Queue] = {}
        _logger.info("IPCBus initialised")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, channel: str, message: Any) -> None:
        """
        Put *message* onto *channel*, creating the channel if necessary.

        Parameters
        ----------
        channel:
            Logical channel name (e.g. ``"events"``, ``"alerts"``).
        message:
            Any Python object to enqueue.
        """
        q = self._get_or_create(channel)
        q.put(message)
        _logger.debug("send channel=%s qsize=%d", channel, q.qsize())

    def receive(
        self,
        channel: str,
        block: bool = False,
        timeout: float = 0.5,
    ) -> Optional[Any]:
        """
        Retrieve one message from *channel*.

        Parameters
        ----------
        channel:
            Channel to read from.
        block:
            If ``True``, wait up to *timeout* seconds for a message.
        timeout:
            Seconds to wait when *block* is ``True``.

        Returns
        -------
        Any or None
            The next message, or ``None`` if the channel is empty.
        """
        q = self._get_or_create(channel)
        try:
            msg = q.get(block=block, timeout=timeout if block else None)
            _logger.debug("receive channel=%s qsize=%d", channel, q.qsize())
            return msg
        except queue.Empty:
            return None

    def list_channels(self) -> List[str]:
        """Return the names of all known channels."""
        return list(self._channels.keys())

    def clear(self, channel: str) -> None:
        """Drain all pending messages from *channel*."""
        q = self._channels.get(channel)
        if q is None:
            return
        drained = 0
        while not q.empty():
            try:
                q.get_nowait()
                drained += 1
            except queue.Empty:
                break
        _logger.debug("clear channel=%s drained=%d", channel, drained)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create(self, channel: str) -> queue.Queue:
        # setdefault is atomic for dict; no lock needed for this check-and-set.
        q = self._channels.setdefault(channel, queue.Queue())
        if q is self._channels[channel]:
            _logger.debug("Accessed channel %s", channel)
        return q
