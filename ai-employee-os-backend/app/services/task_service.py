"""Task business rules."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    UnprocessableError,
)
from app.db.query import Pagination, apply_sort, contains, paginate
from app.models import Customer, Record, Task, User
from app.schemas.task import TaskCreate, TaskFilters, TaskUpdate

logger = logging.getLogger("app.tasks")

TASK_SORT_FIELDS = {
    "created_at": Task.created_at,
    "updated_at": Task.updated_at,
    "due_date": Task.due_date,
    "title": Task.title,
    "status": Task.status,
    # Text order would put 'high' before 'low' before 'medium' before 'urgent'. Rank them instead.
    "priority": case({"urgent": 4, "high": 3, "medium": 2, "low": 1}, value=Task.priority, else_=0),
}

OPEN_STATUSES = ("todo", "in_progress")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_options():
    # Fetch assignee and customer in the same query, so a page of 20 tasks is ONE query, not 41.
    return (joinedload(Task.assignee), joinedload(Task.customer))


def get_task_or_404(db: Session, company_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    stmt = (
        select(Task)
        .options(*_load_options())
        .where(Task.id == task_id, Task.company_id == company_id, Task.deleted_at.is_(None))
    )
    task = db.scalar(stmt)
    if task is None:
        raise NotFoundError("Task not found", code="TASK_NOT_FOUND")
    return task


def _validate_links(db: Session, company_id: uuid.UUID, *, assignee_id=None,
                    customer_id=None, record_id=None) -> None:
    """Every linked object must exist IN THE CALLER'S COMPANY. All problems are reported together."""
    errors: list[dict[str, str]] = []

    if assignee_id is not None:
        assignee = db.get(User, assignee_id)
        if assignee is None or assignee.company_id != company_id or not assignee.is_active:
            errors.append({"field": "assignee_id", "message": "Assignee must be an active user of your company"})

    if customer_id is not None:
        found = db.scalar(select(Customer.id).where(
            Customer.id == customer_id, Customer.company_id == company_id, Customer.deleted_at.is_(None)))
        if found is None:
            errors.append({"field": "customer_id", "message": "Customer not found in your company"})

    if record_id is not None:
        found = db.scalar(select(Record.id).where(
            Record.id == record_id, Record.company_id == company_id, Record.deleted_at.is_(None)))
        if found is None:
            errors.append({"field": "record_id", "message": "Record not found in your company"})

    if errors:
        raise UnprocessableError(errors=errors)


def _validate_schedule(due_date: datetime | None, remind_at: datetime | None) -> None:
    if due_date is not None and remind_at is not None and remind_at > due_date:
        raise UnprocessableError(
            errors=[{"field": "remind_at", "message": "remind_at must not be after due_date"}]
        )


def list_tasks(db: Session, actor: User, filters: TaskFilters, pager: Pagination):
    conditions = [Task.company_id == actor.company_id, Task.deleted_at.is_(None)]

    if filters.statuses:
        conditions.append(Task.status.in_(filters.statuses))
    if filters.priorities:
        conditions.append(Task.priority.in_(filters.priorities))
    if filters.assignee_id:
        conditions.append(Task.assignee_id == filters.assignee_id)
    if filters.mine:
        conditions.append(Task.assignee_id == actor.id)
    if filters.customer_id:
        conditions.append(Task.customer_id == filters.customer_id)
    if filters.due_before:
        conditions.append(Task.due_date <= filters.due_before)
    if filters.due_after:
        conditions.append(Task.due_date >= filters.due_after)
    if filters.overdue:
        conditions.append(Task.due_date < _now())
        conditions.append(Task.status.in_(OPEN_STATUSES))
    if filters.search:
        conditions.append(or_(contains(Task.title, filters.search), contains(Task.description, filters.search)))

    stmt = select(Task).options(*_load_options()).where(*conditions)
    stmt = apply_sort(stmt, pager.sort, TASK_SORT_FIELDS, default="-created_at", tiebreaker=Task.id)
    return paginate(db, stmt, pager)


def create_task(db: Session, actor: User, data: TaskCreate) -> Task:
    _validate_links(db, actor.company_id, assignee_id=data.assignee_id,
                    customer_id=data.customer_id, record_id=data.record_id)
    _validate_schedule(data.due_date, data.remind_at)

    task = Task(company_id=actor.company_id, created_by=actor.id, **data.model_dump())
    if task.status == "done":
        task.completed_at = _now()
    db.add(task)
    db.commit()
    logger.info("Task created: id=%s company=%s source=%s", task.id, actor.company_id, task.source)
    return get_task_or_404(db, actor.company_id, task.id)


def update_task(db: Session, actor: User, task_id: uuid.UUID, data: TaskUpdate) -> Task:
    task = get_task_or_404(db, actor.company_id, task_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequestError("Provide at least one field to update", code="NO_FIELDS_TO_UPDATE")

    # Only re-check links the client is changing: a task whose assignee was deactivated
    # later must still be editable (for example, to reassign it).
    _validate_links(db, actor.company_id, assignee_id=changes.get("assignee_id"),
                    customer_id=changes.get("customer_id"), record_id=changes.get("record_id"))
    # The reminder rule is checked against the values the task will have AFTER the update.
    _validate_schedule(changes.get("due_date", task.due_date), changes.get("remind_at", task.remind_at))

    for field, value in changes.items():
        setattr(task, field, value)

    # completed_at belongs to the server: stamp it on done, clear it when reopened.
    if "status" in changes:
        if task.status == "done" and task.completed_at is None:
            task.completed_at = _now()
        elif task.status != "done":
            task.completed_at = None

    db.commit()
    return get_task_or_404(db, actor.company_id, task.id)


def delete_task(db: Session, actor: User, task_id: uuid.UUID) -> None:
    """Soft delete. Admins and managers may delete any task; a member only the ones they created."""
    task = get_task_or_404(db, actor.company_id, task_id)
    if actor.role == "member" and task.created_by != actor.id:
        raise PermissionDeniedError("Members can only delete tasks they created")
    task.deleted_at = _now()
    db.commit()
    logger.info("Task deleted: id=%s by user=%s", task.id, actor.id)