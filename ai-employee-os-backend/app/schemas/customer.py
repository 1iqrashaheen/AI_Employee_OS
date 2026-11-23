import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.user import UserSummary
from app.schemas.validators import (
    check_phone,
    clean_tags,
    forbid_nulls,
    lowercase_or_none,
    normalize_optional_email,
    strip_or_none,
)

CustomerStage = Literal["lead", "qualified", "proposal", "negotiation", "won", "lost"]
CustomerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class CustomerSummary(BaseModel):
    """A customer embedded in another object (a task)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: CustomerName
    email: EmailStr | None = None
    phone: str | None = None
    organization: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=1000)
    stage: CustomerStage = "lead"
    source: str | None = Field(default=None, max_length=30)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=5000)
    owner_id: uuid.UUID | None = None

    _email = field_validator("email", mode="before")(normalize_optional_email)
    _phone = field_validator("phone")(check_phone)
    _text = field_validator("organization", "address", "notes")(strip_or_none)
    _source = field_validator("source")(lowercase_or_none)
    _tags = field_validator("tags")(clean_tags)


class CustomerUpdate(BaseModel):
    """PATCH body: every field optional. name, stage and tags cannot be set to null."""

    model_config = ConfigDict(extra="forbid")

    name: CustomerName | None = None
    email: EmailStr | None = None
    phone: str | None = None
    organization: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=1000)
    stage: CustomerStage | None = None
    source: str | None = Field(default=None, max_length=30)
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=5000)
    owner_id: uuid.UUID | None = None

    _email = field_validator("email", mode="before")(normalize_optional_email)
    _phone = field_validator("phone")(check_phone)
    _text = field_validator("organization", "address", "notes")(strip_or_none)
    _source = field_validator("source")(lowercase_or_none)
    _tags = field_validator("tags")(clean_tags)

    @model_validator(mode="after")
    def required_fields_not_null(self):
        forbid_nulls(self, ("name", "stage", "tags"))
        return self


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    organization: str | None
    address: str | None
    stage: str
    source: str | None
    tags: list[str]
    notes: str | None
    owner_id: uuid.UUID | None
    owner: UserSummary | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

class TimelineItem(BaseModel):
    """One entry in a customer's history: a task or a record (quotation, invoice, note...)."""

    kind: Literal["task", "record"]
    id: uuid.UUID
    type: str | None  # the record type for records, null for tasks
    title: str | None
    status: str
    at: datetime