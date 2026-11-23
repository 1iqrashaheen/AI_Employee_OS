import re
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

# A name: trimmed, 2-150 characters. (Applied per field so passwords are NEVER trimmed.)
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]


def _check_password_strength(value: str) -> str:
    """Rules for NEW passwords (register / change-password). Not applied at login."""
    # bcrypt only uses the first 72 BYTES. Reject longer passwords instead of silently cutting them.
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes long")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one number")
    return value


def _normalize_email(value):
    """Trim and lowercase emails so 'Ali@Acme.com ' and 'ali@acme.com' are the same account."""
    return value.strip().lower() if isinstance(value, str) else value


# ------------------------------- requests ---------------------------------- #
class RegisterRequest(BaseModel):
    company_name: Name
    full_name: Name
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    _normalize_email = field_validator("email", mode="before")(_normalize_email)

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return _check_password_strength(value)


class LoginRequest(BaseModel):
    email: EmailStr
    # No strength rules here: we only compare. max_length stops absurdly large inputs.
    password: str = Field(min_length=1, max_length=128)

    _normalize_email = field_validator("email", mode="before")(_normalize_email)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return _check_password_strength(value)

    @model_validator(mode="after")
    def passwords_differ(self):
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current password")
        return self


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    _normalize_email = field_validator("email", mode="before")(_normalize_email)


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return _check_password_strength(value)


# ------------------------------- responses --------------------------------- #
class UserOut(BaseModel):
    """A user as the API shows it. password_hash and token_version are never included."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    full_name: str
    email: str
    role: str
    phone: str | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    plan: str
    is_active: bool


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class PasswordResetData(BaseModel):
    """Reset delivery is omitted; send reset links only through a verified provider."""
    sent: bool = True


class AuthData(TokenPair):
    """Register / login: the tokens plus who just logged in."""

    user: UserOut
    company: CompanyOut


class MeData(BaseModel):
    user: UserOut
    company: CompanyOut

