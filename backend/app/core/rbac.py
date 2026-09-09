"""RBAC policies and shared permission helpers."""
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.models.user import Role, User

# Role capabilities matrix (simplified)
ROLE_CAPABILITIES: dict[Role, set[str]] = {
    Role.ADMIN: {"admin", "audit", "export", "ingest", "minors", "all_data", "commission"},
    Role.OBLAST_PROSECUTOR: {"audit", "export", "minors", "all_data", "commission"},
    Role.DEPUTY_PROSECUTOR: {"export", "minors", "all_data", "commission"},
    Role.DEPARTMENT_HEAD: {"export", "all_data"},
    Role.ANALYST: {"export", "ingest", "all_data", "commission"},
    Role.DISTRICT_PROSECUTOR: {"export", "district_only", "commission"},
    Role.OSINT_USER: set(),
    Role.SECURITY_AUDITOR: {"audit"},
}


def has_capability(user: User, cap: str) -> bool:
    return cap in ROLE_CAPABILITIES.get(user.role, set())


def require_capability(cap: str) -> Callable:
    def checker(user: User = Depends(get_current_user)) -> User:
        if not has_capability(user, cap):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Недостаточно прав: {cap}")
        return user
    return checker


def allow_pii(user: User) -> bool:
    return user.can_access_minors or has_capability(user, "minors") or user.role in (
        Role.OBLAST_PROSECUTOR, Role.DEPUTY_PROSECUTOR, Role.ANALYST, Role.DISTRICT_PROSECUTOR,
    )
