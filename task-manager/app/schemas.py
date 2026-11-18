"""Request/response shapes for the Task Manager module.

Field names, allowed values and rules follow Hadeed's backend design
(ai-employee-os-backend/docs/backend-research-and-design.md, sections 4.2 and 4.9)
so this module can be switched onto the shared database later without changing
what the frontend or other modules see.
"""
from datetime import datetime, timezone
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

TaskStatus = Literal["todo", "in_progress", "done", "cancelled"]
TaskPriority = Literal["low", "medium", "high", "urgent"]
TaskSource = Literal["manual", "ai_agent", "automation"]

OPEN_STATUSES = ("todo", "in_progress")
PRIORITY_RANK = {"urgent": 0, "high": 1, "medium": 2, "low": 3}


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Dates are stored in UTC. A date sent without a timezone is treated as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _clean_title(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Title cannot be empty")
    return value


class TaskCreate(BaseModel):
    title: str = Field(max_length=200)
    description: Optional[str] = None
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    due_date: Optional[datetime] = None
    remind_at: Optional[datetime] = None
    assignee_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    record_id: Optional[UUID] = None
    source: TaskSource = "manual"

    _title = field_validator("title")(_clean_title)
    _dates = field_validator("due_date", "remind_at")(_as_utc)


class TaskUpdate(BaseModel):
    """PATCH body: only the fields that are sent are changed.

    Sending ``"due_date": null`` clears the date, leaving it out keeps it.
    """

    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    remind_at: Optional[datetime] = None
    assignee_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    record_id: Optional[UUID] = None

    _title = field_validator("title")(_clean_title)
    _dates = field_validator("due_date", "remind_at")(_as_utc)


class Task(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    status: TaskStatus
    priority: TaskPriority
    due_date: Optional[datetime] = None
    remind_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    assignee_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    record_id: Optional[UUID] = None
    source: TaskSource = "manual"
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = Field(default=None, exclude=True)


class TaskView(Task):
    """A task as returned by the API: the stored fields plus computed ones."""

    is_overdue: bool = False
    assignee_name: Optional[str] = None


class Reminder(BaseModel):
    reminder_type: Literal["overdue", "due_soon", "reminder"]
    message: str
    task: TaskView


class Assignee(BaseModel):
    id: UUID
    full_name: str
    role: Literal["admin", "manager", "member"]


class ListFilters(BaseModel):
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    due_before: Optional[datetime] = None
    due_after: Optional[datetime] = None
    overdue: bool = False
    search: Optional[str] = None
    sort: str = "-created_at"
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)

    _dates = field_validator("due_before", "due_after")(_as_utc)


class ProgressSummary(BaseModel):
    total: int
    by_status: dict
    open_by_priority: dict
    completed_percent: float
    overdue: int
    due_soon: int


class FieldError(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    success: bool = False
    message: str
    code: str
    errors: List[FieldError] = []
