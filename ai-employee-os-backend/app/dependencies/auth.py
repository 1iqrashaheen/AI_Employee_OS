"""
Route protection.

    @router.get("/something")
    def something(user: CurrentUser): ...       # any logged-in user

    @router.get("/admin-only")
    def admin_only(user: AdminUser): ...        # admins only

Why dependencies instead of a global middleware? A middleware would run on EVERY URL
(including login and health) and cannot say which routes need which role. A dependency
is attached per route, shows in Swagger as a padlock, and hands the endpoint the user.
"""
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_token
from app.dependencies.db import DbSession
from app.models import User
from app.services.auth_service import load_user_from_payload

# auto_error=False: we raise our OWN 401 so it uses the standard error format.
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Paste the access_token only (without the word 'Bearer').",
)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    """Resolve 'Authorization: Bearer <access_token>' into the active database user."""
    if credentials is None:
        raise AuthenticationError(
            "Missing Authorization header. Send: Authorization: Bearer <access_token>",
            code="AUTH_REQUIRED",
        )
    payload = decode_token(credentials.credentials, expected_type="access")
    return load_user_from_payload(db, payload)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: str):
    """Build a dependency that only lets the given roles through (otherwise 403)."""

    def role_checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise PermissionDeniedError(
                f"This action requires one of these roles: {', '.join(allowed_roles)}. "
                f"Your role is '{current_user.role}'."
            )
        return current_user

    return role_checker


# Ready-made shortcuts for the routers
AdminUser = Annotated[User, Depends(require_roles("admin"))]
ManagerOrAdmin = Annotated[User, Depends(require_roles("admin", "manager"))]