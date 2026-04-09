# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Identity — Session management."""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from aura.utils import get_logger, utcnow

if TYPE_CHECKING:
    from aura.identity.user import User

_logger = get_logger("aura.identity.session")


def _hours_from_now(hours: int) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(hours=hours)
    ).isoformat()


@dataclass
class Session:
    session_id: str
    user_id: str
    username: str
    role: str
    created_at: str
    expires_at: str
    active: bool = True

    def is_expired(self) -> bool:
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) >= exp
        except Exception:
            return True

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "active": self.active,
        }


class SessionManager:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self, user: "User", ttl_hours: int = 24) -> Session:
        session = Session(
            session_id=secrets.token_urlsafe(32),
            user_id=user.user_id,
            username=user.username,
            role=user.role.value,
            created_at=utcnow(),
            expires_at=_hours_from_now(ttl_hours),
        )
        with self._lock:
            self._sessions[session.session_id] = session
        _logger.debug("Session created for user %s", user.username)
        return session

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            session = self._sessions.get(session_id)
        if session and (not session.active or session.is_expired()):
            return None
        return session

    def invalidate(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.active = False
                return True
        return False

    def list_active(self) -> List[dict]:
        with self._lock:
            sessions = list(self._sessions.values())
        return [
            s.to_dict()
            for s in sessions
            if s.active and not s.is_expired()
        ]

    def cleanup_expired(self) -> int:
        with self._lock:
            expired = [
                sid
                for sid, s in self._sessions.items()
                if not s.active or s.is_expired()
            ]
            for sid in expired:
                del self._sessions[sid]
        return len(expired)
