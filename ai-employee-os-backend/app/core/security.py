"""
Security primitives: password hashing (bcrypt) and JSON Web Tokens (PyJWT).
No database or HTTP code lives here, so it is easy to test.

TOKEN CLAIMS
  sub   user id (a STRING; PyJWT requires it)
  cid   company id          (access token only)
  role  role at issue time  (access token only, informational: the DB is the truth)
  ver   user's token_version. If the user's version in the DB changes
        (password change), every older token stops working.
  type  "access" or "refresh". Stops one being used as the other.
  iat / exp / jti   issued-at, expiry, unique token id
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import TokenExpiredError, TokenInvalidError

TokenType = Literal["access", "refresh", "reset"]


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(plain_password: str) -> str:
    """
    Hash a password with bcrypt. The random salt is stored inside the hash string.
    The password must be at most 72 bytes: the schema validation guarantees this.
    """
    hashed = bcrypt.hashpw(
        plain_password.encode("utf-8"),
        bcrypt.gensalt(rounds=settings.bcrypt_rounds),
    )
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password against its stored hash. Never raises: bad input is just False."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # e.g. password longer than 72 bytes, or a corrupted hash
        return False


# Used when the email does not exist: we still do one bcrypt check so a login for an
# unknown email takes the same time as a wrong password (prevents email discovery).
DUMMY_PASSWORD_HASH = hash_password("timing-attack-protection-password-1")


# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
def _encode(claims: dict[str, Any], lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**claims, "iat": now, "exp": now + lifetime, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(
    *,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
    role: str,
    token_version: int,
    expires_delta: timedelta | None = None,  # only used by tests
) -> str:
    lifetime = expires_delta if expires_delta is not None else timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return _encode(
        {
            "sub": str(user_id),
            "cid": str(company_id),
            "role": role,
            "ver": token_version,
            "type": "access",
        },
        lifetime,
    )


def create_refresh_token(
    *,
    user_id: uuid.UUID,
    token_version: int,
    expires_delta: timedelta | None = None,
) -> str:
    lifetime = expires_delta if expires_delta is not None else timedelta(
        days=settings.refresh_token_expire_days
    )
    return _encode({"sub": str(user_id), "ver": token_version, "type": "refresh"}, lifetime)


def create_reset_token(*, user_id: uuid.UUID, token_version: int) -> str:
    """Create a short-lived, single-purpose password reset token."""
    return _encode(
        {"sub": str(user_id), "ver": token_version, "type": "reset"},
        timedelta(minutes=settings.reset_token_expire_minutes),
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """
    Verify signature + expiry + required claims + token type.
    Raises TokenExpiredError / TokenInvalidError (both become HTTP 401).
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],  # ALWAYS pin the algorithm (blocks "alg: none" tricks)
            options={"require": ["exp", "sub", "type", "ver"]},
        )
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError() from None
    except jwt.InvalidTokenError:  # bad signature, malformed, missing claim...
        raise TokenInvalidError() from None

    if payload.get("type") != expected_type:
        raise TokenInvalidError(f"Wrong token type: an {expected_type} token is required.")
    return payload