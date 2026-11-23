import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.validators import (
    Name,
    check_password_strength,
    check_phone,
    forbid_nulls,
    normalize_email,
)

UserRole = Literal["admin", "manager", "member"]


class UserSummary(BaseModel):
    """A person embedded in another object (task assignee, customer owner) or in the directory."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields

    full_name: Name
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "member"
    phone: str | None = None

    _email = field_validator("email", mode="before")(normalize_email)
    _phone = field_validator("phone")(check_phone)

    @field_validator("password")
    @classmethod
    def password_is_strong(cls, value: str) -> str:
        return check_password_strength(value)


class UserUpdate(BaseModel):
    """PATCH body. The email is deliberately not editable (it is the login)."""

    model_config = ConfigDict(extra="forbid")

    full_name: Name | None = None
    phone: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None

    _phone = field_validator("phone")(check_phone)

    @model_validator(mode="after")
    def required_fields_not_null(self):
        forbid_nulls(self, ("full_name", "role", "is_active"))
        return self