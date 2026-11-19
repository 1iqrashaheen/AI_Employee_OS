"""Authentication endpoints. All paths are under /api/v1/auth."""
from fastapi import APIRouter

from app.dependencies.auth import AdminUser, CurrentUser
from app.dependencies.db import DbSession
from app.schemas.auth import (
    AuthData,
    ChangePasswordRequest,
    CompanyOut,
    LoginRequest,
    MeData,
    RefreshRequest,
    RegisterRequest,
    RoleCheckData,
    TokenPair,
    UserOut,
)
from app.schemas.common import ApiResponse, ErrorResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Error documentation shown in Swagger
_E401 = {"model": ErrorResponse, "description": "Missing, invalid, expired or revoked token"}
_E403 = {"model": ErrorResponse, "description": "Not allowed (role, or account/company disabled)"}
_E422 = {"model": ErrorResponse, "description": "Validation failed"}


def _auth_data(user, company, tokens: TokenPair) -> AuthData:
    return AuthData(
        **tokens.model_dump(),
        user=UserOut.model_validate(user),
        company=CompanyOut.model_validate(company),
    )


@router.post(
    "/register",
    response_model=ApiResponse[AuthData],
    status_code=201,
    summary="Create a company and its first admin user",
    responses={409: {"model": ErrorResponse, "description": "Email already registered"}, 422: _E422},
)
def register(payload: RegisterRequest, db: DbSession):
    # `def` (not `async def`): FastAPI runs it in a thread pool, so slow bcrypt hashing
    # and the synchronous database calls never block other requests.
    user, company = auth_service.register_company_admin(db, payload)
    tokens = auth_service.build_token_pair(user)
    return ApiResponse[AuthData](
        message="Account created successfully",
        data=_auth_data(user, company, tokens),
    )


@router.post(
    "/login",
    response_model=ApiResponse[AuthData],
    summary="Log in with email and password",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid email or password"},
        403: _E403,
        422: _E422,
    },
)
def login(payload: LoginRequest, db: DbSession):
    user, company = auth_service.authenticate_user(db, payload.email, payload.password)
    tokens = auth_service.build_token_pair(user)
    return ApiResponse[AuthData](
        message="Login successful",
        data=_auth_data(user, company, tokens),
    )


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenPair],
    summary="Exchange a refresh token for a new token pair",
    responses={401: _E401, 403: _E403, 422: _E422},
)
def refresh(payload: RefreshRequest, db: DbSession):
    user = auth_service.refresh_session(db, payload.refresh_token)
    return ApiResponse[TokenPair](
        message="Token refreshed successfully",
        data=auth_service.build_token_pair(user),
    )


@router.get(
    "/me",
    response_model=ApiResponse[MeData],
    summary="Get the logged-in user and company",
    responses={401: _E401, 403: _E403},
)
def me(current_user: CurrentUser, db: DbSession):
    company = auth_service.get_company(db, current_user.company_id)
    return ApiResponse[MeData](
        data=MeData(
            user=UserOut.model_validate(current_user),
            company=CompanyOut.model_validate(company),
        ),
    )


@router.post(
    "/change-password",
    response_model=ApiResponse[TokenPair],
    summary="Change password (revokes all old tokens, returns new ones)",
    responses={
        400: {"model": ErrorResponse, "description": "Current password is incorrect"},
        401: _E401,
        403: _E403,
        422: _E422,
    },
)
def change_password(payload: ChangePasswordRequest, current_user: CurrentUser, db: DbSession):
    auth_service.change_password(
        db, current_user, payload.current_password, payload.new_password
    )
    # The old tokens are dead now, so hand back a fresh pair to keep this session alive.
    return ApiResponse[TokenPair](
        message="Password changed successfully",
        data=auth_service.build_token_pair(current_user),
    )


@router.get(
    "/admin-check",
    response_model=ApiResponse[RoleCheckData],
    summary="Demo: admins only (used to test role protection)",
    responses={401: _E401, 403: _E403},
)
def admin_check(admin: AdminUser):
    # Temporary: remove once real admin-only endpoints exist (Day 5, Users API).
    return ApiResponse[RoleCheckData](
        message="You are an admin",
        data=RoleCheckData(user_id=admin.id, role=admin.role),
    )