# Copyright (c) 2024-2026 AURa Project (Cbetts1/Damn-it-xm). All rights reserved.
# SPDX-License-Identifier: MIT
"""AURa Package Manager — package metadata and status definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class PackageStatus(Enum):
    AVAILABLE = "available"
    INSTALLED = "installed"
    UPGRADABLE = "upgradable"
    BROKEN = "broken"
    NOT_FOUND = "not_found"


@dataclass
class PackageMetadata:
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    license: str = "MIT"
    size_bytes: int = 0
    checksum: str = ""
    created_at: str = ""
    homepage: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "license": self.license,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "homepage": self.homepage,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PackageMetadata:
        return cls(
            name=d["name"],
            version=d["version"],
            description=d.get("description", ""),
            author=d.get("author", ""),
            dependencies=d.get("dependencies", []),
            tags=d.get("tags", []),
            license=d.get("license", "MIT"),
            size_bytes=d.get("size_bytes", 0),
            checksum=d.get("checksum", ""),
            created_at=d.get("created_at", ""),
            homepage=d.get("homepage", ""),
        )
