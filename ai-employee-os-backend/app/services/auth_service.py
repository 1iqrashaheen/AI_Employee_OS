"""
Authentication business logic. Routers call these functions, and these functions
raise AppException subclasses on failure.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AccountDisabledError,
    BadRequestError,
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
    TokenInvalidError,
    TokenRevokedError,
)
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import Company, User
from app.schemas.auth import RegisterRequest, TokenPair

logger = logging.getLogger("app.auth")


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def get_user_by_email(db: Session, email: str) -> User | None:
    # Emails are stored lowercase (the schema normalizes them), so plain equality works.
    return db.scalar(select(User).where(User.email == email))


def get_company(db: Session, company_id: uuid.UUID) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company not found", code="COMPANY_NOT_FOUND")
    return company


def build_token_pair(user: User) -> TokenPair:
    """Create a fresh access + refresh token for a user."""
    return TokenPair(
        access_token=create_access_token(
            user_id=user.id,
            company_id=user.company_id,
            role=user.role,
            token_version=user.token_version,
        ),
        refresh_token=create_refresh_token(user_id=user.id, token_version=user.token_version),
        expires_in=settings.access_token_expire_minutes * 60,
    )


def _ensure_company_active(db: Session, user: User) -> Company:
    company = db.get(Company, user.company_id)
    if company is None or not company.is_active:
        raise AccountDisabledError(
            "Your company account is disabled. Please contact support.",
            code="COMPANY_DISABLED",
        )
    return company


# --------------------------------------------------------------------------- #
# Use cases
# --------------------------------------------------------------------------- #
def register_company_admin(db: Session, data: RegisterRequest) -> tuple[User, Company]:
    """Create a company and its first user (an admin) in ONE transaction."""
    if get_user_by_email(db, data.email) is not None:
        raise ConflictError(
            "An account with this email already exists",
            code="EMAIL_ALREADY_REGISTERED",
        )

    # Hash BEFORE opening the transaction: bcrypt is slow and we don't want to hold DB locks.
    password_hash = hash_password(data.password)

    try:
        company = Company(name=data.company_name, email=data.email)
        db.add(company)
        db.flush()  # sends the INSERT so company.id exists, but does not commit yet

        user = User(
            company_id=company.id,
            full_name=data.full_name,
            email=data.email,
            password_hash=password_hash,
            role="admin",  # the person who creates the company is its admin
        )
        db.add(user)
        db.commit()  # both rows are saved together, or neither is
    except IntegrityError:
        # Two people registering the same email at the same moment: the unique
        # constraint in the database is the final safety net.
        db.rollback()
        raise ConflictError(
            "An account with this email already exists",
            code="EMAIL_ALREADY_REGISTERED",
        ) from None

    db.refresh(user)
    db.refresh(company)
    logger.info("New company registered: company_id=%s user_id=%s", company.id, user.id)
    return user, company


def authenticate_user(db: Session, email: str, password: str) -> tuple[User, Company]:
    """Check email + password. The same error is used for 'no such email' and 'wrong password'."""
    user = get_user_by_email(db, email)

    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)  # equalize timing, ignore the result
        raise InvalidCredentialsError()
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()

    # Only someone who knows the correct password learns the account is disabled.
    if not user.is_active:
        raise AccountDisabledError()
    company = _ensure_company_active(db, user)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user, company


def load_user_from_payload(db: Session, payload: dict) -> User:
    """
    Turn verified token claims into the current database user, re-checking everything
    that can change after a token was issued. Used by get_current_user AND refresh.
    """
    try:
        user_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, ValueError):
        raise TokenInvalidError() from None

    user = db.get(User, user_id)
    if user is None:
        raise TokenInvalidError("The account for this token no longer exists.")
    if payload.get("ver") != user.token_version:
        raise TokenRevokedError()
    if not user.is_active:
        raise AccountDisabledError()
    _ensure_company_active(db, user)
    return user


def refresh_session(db: Session, refresh_token: str) -> User:
    """Validate a refresh token and return its user (the router then issues new tokens)."""
    payload = decode_token(refresh_token, expected_type="refresh")
    return load_user_from_payload(db, payload)


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    """
    Change the password and revoke every existing token by bumping token_version.
    A wrong current password is a 400 (not 401) so frontends don't log the user out.
    """
    if not verify_password(current_password, user.password_hash):
        raise BadRequestError("Current password is incorrect", code="INVALID_CURRENT_PASSWORD")

    user.password_hash = hash_password(new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    logger.info("Password changed: user_id=%s (all older tokens revoked)", user.id)


def logout(db: Session, user: User) -> None:
    """Revoke every access and refresh token belonging to the current user."""
    user.token_version += 1
    db.commit()
    db.refresh(user)
    logger.info("User logged out: user_id=%s (all tokens revoked)", user.id)


def create_password_reset(db: Session, email: str) -> str | None:
    """
    Create a reset token without disclosing whether the email exists.
    The caller decides whether to expose or deliver the token.
    """
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    company = db.get(Company, user.company_id)
    if company is None or not company.is_active:
        return None
    return create_reset_token(user_id=user.id, token_version=user.token_version)


def reset_password(db: Session, reset_token: str, new_password: str) -> None:
    payload = decode_token(reset_token, expected_type="reset")
    user = load_user_from_payload(db, payload)
    user.password_hash = hash_password(new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)
    logger.info("Password reset: user_id=%s (all older tokens revoked)", user.id)