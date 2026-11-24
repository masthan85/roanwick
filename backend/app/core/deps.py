import uuid
from collections.abc import Callable
from typing import Annotated, Generic, TypeVar

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import Forbidden, Unauthorised
from app.core.security import decode_token
from app.models.identity import AuditEvent, Permission, RolePermission, User, UserRole

bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]


def current_user(request: Request, db: DB, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    if creds is None:
        raise Unauthorised("Please sign in to continue.")
    try:
        payload = decode_token(creds.credentials, "access")
        user = db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise Unauthorised("Your session has expired. Please sign in again.")
    if user is None or not user.is_active or user.anonymised_at:
        raise Unauthorised("This account is not active.")
    request.state.user = user
    return user


def optional_user(request: Request, db: DB, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User | None:
    if creds is None:
        return None
    return current_user(request, db, creds)


CurrentUser = Annotated[User, Depends(current_user)]
MaybeUser = Annotated[User | None, Depends(optional_user)]


def require_role(*roles: str) -> Callable:
    def dep(user: CurrentUser) -> User:
        if not set(roles) & set(user.role_keys):
            raise Forbidden("You do not have access to this area.")
        return user

    return dep


Customer = Annotated[User, Depends(require_role("customer"))]
Provider = Annotated[User, Depends(require_role("provider"))]


def user_permissions(db: Session, user: User) -> set[str]:
    rows = db.execute(
        select(Permission.key)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user.id)
    ).scalars()
    return set(rows)


def require_permission(*perms: str) -> Callable:
    """Staff must hold every listed permission."""

    def dep(user: CurrentUser, db: DB) -> User:
        held = user_permissions(db, user)
        if not set(perms) <= held:
            raise Forbidden("You do not have permission to do that.")
        from app.services.config_store import get_setting

        if get_setting(db, "require_staff_mfa") and not user.mfa_enabled_at:
            raise Forbidden("Turn on two-step verification in Security to use the admin console.", code="mfa_enrolment_required")
        return user

    return dep


def audit(db: Session, request: Request | None, actor: User | None, action: str, entity_type: str, entity_id, before=None, after=None) -> None:
    db.add(
        AuditEvent(
            at=utcnow(),
            actor_user_id=actor.id if actor else None,
            actor_role=",".join(actor.role_keys) if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=before,
            after=after,
            ip=(request.client.host if request and request.client else None),
            request_id=getattr(request.state, "request_id", None) if request else None,
        )
    )


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(self, page: int = Query(1, ge=1, le=10000), page_size: int = Query(20, ge=1, le=100)):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


Pagination = Annotated[PageParams, Depends()]


def paginate(db: Session, stmt, params: PageParams, convert: Callable | None = None) -> dict:
    total = db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.execute(stmt.limit(params.page_size).offset(params.offset)).scalars().unique().all()
    items = [convert(r) for r in rows] if convert else rows
    return {"items": items, "total": total, "page": params.page, "page_size": params.page_size}
