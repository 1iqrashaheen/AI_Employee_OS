import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    field_validator,
    model_validator,
)

from app.schemas.customer import CustomerSummary
from app.schemas.user import UserSummary
from app.schemas.validators import forbid_nulls, strip_or_none

TaskStatus = Literal["todo", "in_progress", "done", "cancelled"]
TaskPriority = Literal["low", "medium", "high", "urgent"]
TaskSource = Literal["manual", "ai_agent", "automation"]
TaskTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]

# AwareDatetime rejects dates WITHOUT a timezone ("2026-11-24T09:00:00"). A deadline with no
# timezone is ambiguous, so clients must send "...Z" or an offset such as "+05:00".


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TaskTitle
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    due_date: AwareDatetime | None = None
    remind_at: AwareDatetime | None = None
    assignee_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    record_id: uuid.UUID | None = None
    source: TaskSource = "manual"

    _description = field_validator("description")(strip_or_none)


class TaskUpdate(BaseModel):
    """PATCH body. `source` and `completed_at` cannot be changed by clients."""

    model_config = ConfigDict(extra="forbid")

    title: TaskTitle | None = None
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: AwareDatetime | None = None
    remind_at: AwareDatetime | None = None
    assignee_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    record_id: uuid.UUID | None = None

    _description = field_validator("description")(strip_or_none)

    @model_validator(mode="after")
    def required_fields_not_null(self):
        forbid_nulls(self, ("title", "status", "priority"))
        return self


@dataclass
class TaskFilters:
    """The ?query parameters of GET /tasks, collected into one object."""

    statuses: list[str] | None = None
    priorities: list[str] | None = None
    assignee_id: uuid.UUID | None = None
    mine: bool = False
    customer_id: uuid.UUID | None = None
    due_before: datetime | None = None
    due_after: datetime | None = None
    overdue: bool = False
    search: str | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    description: str | None
    status: str
    priority: str
    due_date: datetime | None
    remind_at: datetime | None
    completed_at: datetime | None
    assignee_id: uuid.UUID | None
    assignee: UserSummary | None
    customer_id: uuid.UUID | None
    customer: CustomerSummary | None
    record_id: uuid.UUID | None
    source: str
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_overdue(self) -> bool:
        """True when the deadline has passed and the task is still open."""
        return (
            self.due_date is not None
            and self.status in ("todo", "in_progress")
            and self.due_date < datetime.now(timezone.utc)
        )