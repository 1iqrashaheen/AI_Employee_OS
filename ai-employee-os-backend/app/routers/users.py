"""User management endpoints. All paths are under /api/v1/users."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.dependencies.auth import AdminUser, CurrentUser, ManagerOrAdmin
from app.dependencies.db import DbSession
from app.dependencies.pagination import Pager
from app.routers.responses import error_responses
from app.schemas.auth import UserOut
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.user import UserCreate, UserRole, UserSummary, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=PaginatedResponse[UserOut],
            summary="List users (admin, manager)", responses=error_responses(401, 403, 422))
def list_users(
    actor: ManagerOrAdmin, db: DbSession, pager: Pager,
    search: Annotated[str | None, Query(max_length=100, description="Matches name or email")] = None,
    role: Annotated[UserRole | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
):
    users, meta = user_service.list_users(db, actor, search=search, role=role, is_active=is_active, pager=pager)
    return PaginatedResponse[UserOut](data=[UserOut.model_validate(u) for u in users], meta=meta)


# NOTE: declared BEFORE "/{user_id}", otherwise "directory" would be read as a user id.
@router.get("/directory", response_model=PaginatedResponse[UserSummary],
            summary="Active users, names only (any role): for assignee dropdowns",
            responses=error_responses(401, 403, 422))
def user_directory(
    actor: CurrentUser, db: DbSession, pager: Pager,
    search: Annotated[str | None, Query(max_length=100, description="Matches name")] = None,
):
    users, meta = user_service.list_directory(db, actor, search=search, pager=pager)
    return PaginatedResponse[UserSummary](data=[UserSummary.model_validate(u) for u in users], meta=meta)


@router.post("", response_model=ApiResponse[UserOut], status_code=201,
             summary="Create a team member (admin)", responses=error_responses(401, 403, 409, 422))
def create_user(payload: UserCreate, actor: AdminUser, db: DbSession):
    user = user_service.create_user(db, actor, payload)
    return ApiResponse[UserOut](message="User created successfully", data=UserOut.model_validate(user))


@router.get("/{user_id}", response_model=ApiResponse[UserOut],
            summary="Get one user (members: only themselves)", responses=error_responses(401, 403, 404, 422))
def get_user(user_id: uuid.UUID, actor: CurrentUser, db: DbSession):
    return ApiResponse[UserOut](data=UserOut.model_validate(user_service.get_user(db, actor, user_id)))


@router.patch("/{user_id}", response_model=ApiResponse[UserOut],
              summary="Update a user (partial)", responses=error_responses(400, 401, 403, 404, 422))
def update_user(user_id: uuid.UUID, payload: UserUpdate, actor: CurrentUser, db: DbSession):
    user = user_service.update_user(db, actor, user_id, payload)
    return ApiResponse[UserOut](message="User updated successfully", data=UserOut.model_validate(user))


@router.delete("/{user_id}", response_model=ApiResponse[UserOut],
               summary="Deactivate a user (admin)", responses=error_responses(400, 401, 403, 404))
def deactivate_user(user_id: uuid.UUID, actor: AdminUser, db: DbSession):
    user = user_service.deactivate_user(db, actor, user_id)
    return ApiResponse[UserOut](message="User deactivated", data=UserOut.model_validate(user))