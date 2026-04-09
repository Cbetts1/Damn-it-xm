# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Identity — User model and Role definitions."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from aura.utils import get_logger, generate_id, utcnow

_logger = get_logger("aura.identity.user")


class Role(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    USER = "user"
    GUEST = "guest"


@dataclass
class User:
    user_id: str
    username: str
    role: Role
    password_hash: str   # sha256 hex — never store plaintext
    quota_cpu_cores: float = 0.0
    quota_ram_mb: float = 0.0
    quota_tasks: int = 0
    created_at: str = field(default_factory=utcnow)
    active: bool = True

    def to_dict(self) -> dict:
        """Return serialisable dict, excluding password_hash."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role.value,
            "quota_cpu_cores": self.quota_cpu_cores,
            "quota_ram_mb": self.quota_ram_mb,
            "quota_tasks": self.quota_tasks,
            "created_at": self.created_at,
            "active": self.active,
        }

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @classmethod
    def create(
        cls,
        username: str,
        password: str,
        role: Role = Role.USER,
        quota_cpu_cores: float = 0.0,
        quota_ram_mb: float = 0.0,
        quota_tasks: int = 0,
    ) -> "User":
        return cls(
            user_id=generate_id("user"),
            username=username,
            role=role,
            password_hash=cls.hash_password(password),
            quota_cpu_cores=quota_cpu_cores,
            quota_ram_mb=quota_ram_mb,
            quota_tasks=quota_tasks,
        )
