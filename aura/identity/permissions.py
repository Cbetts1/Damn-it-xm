# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Identity — Role-based permission gate."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from aura.utils import get_logger

if TYPE_CHECKING:
    from aura.identity.user import User

_logger = get_logger("aura.identity.permissions")


class Action(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


# Role-based permission matrix
# Columns: READ, WRITE, EXECUTE, ADMIN
_PERMISSIONS: dict[str, set[Action]] = {
    "admin": {Action.READ, Action.WRITE, Action.EXECUTE, Action.ADMIN},
    "operator": {Action.READ, Action.WRITE, Action.EXECUTE},
    "user": {Action.READ, Action.EXECUTE},
    "guest": {Action.READ},
}


class PermissionGate:
    """Checks role-based permissions for users on resources."""

    def can(self, user: "User", action: Action, resource: str = "*") -> bool:
        """Return True if *user* is allowed to perform *action* on *resource*."""
        role = user.role.value if hasattr(user.role, "value") else str(user.role)
        allowed = _PERMISSIONS.get(role, set())
        return action in allowed

    def require(self, user: "User", action: Action, resource: str = "*") -> None:
        """Raise PermissionError if *user* cannot perform *action* on *resource*."""
        if not self.can(user, action, resource):
            raise PermissionError(
                f"User {user.username!r} (role={user.role}) "
                f"is not permitted to perform action={action.value!r} "
                f"on resource={resource!r}"
            )
