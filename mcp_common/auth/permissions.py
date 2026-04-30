from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Permission(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


@dataclass
class Role:
    name: str
    permissions: frozenset[Permission] = field(default_factory=frozenset)

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "reader": frozenset({Permission.READ}),
    "operator": frozenset({Permission.READ, Permission.WRITE}),
    "admin": frozenset(Permission),
}
