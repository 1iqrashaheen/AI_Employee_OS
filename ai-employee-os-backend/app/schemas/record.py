import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.validators import forbid_nulls

RecordType = Literal["quotation", "invoice", "payment", "meeting_summary", "note", "activity"]
RecordStatus = Literal["draft", "pending", "approved", "paid", "cancelled", "completed"]
RecordSource = Literal["manual", "ai_agent", "automation"]


class RecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: RecordType
    customer_id: uuid.UUID
    task_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    reference_no: str | None = Field(default=None, max_length=50)
    status: RecordStatus = "draft"
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    data: dict = Field(default_factory=dict)
    source: RecordSource = "manual"


class RecordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: RecordType | None = None
    customer_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=200)
    reference_no: str | None = Field(default=None, max_length=50)
    status: RecordStatus | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    data: dict | None = None

    @model_validator(mode="after")
    def required_fields_not_null(self):
        forbid_nulls(self, ("type", "customer_id", "status", "currency", "data"))
        return self


class RecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    type: str
    title: str | None
    reference_no: str | None
    status: str
    amount: Decimal | None
    currency: str
    data: dict
    customer_id: uuid.UUID | None
    task_id: uuid.UUID | None
    source: str
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
