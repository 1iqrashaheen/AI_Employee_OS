"""Business rules for tasks: create, edit, complete, filter, remind, progress.

Every function that depends on the time takes ``now`` as an argument instead of
reading the clock, so the tests can check "overdue" and "due soon" exactly.
"""
import math
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from .schemas import (
    OPEN_STATUSES,
    AssigneeSummary,
    PRIORITY_RANK,
    ListFilters,
    ProgressSummary,
    Reminder,
    Task,
    TaskCreate,
    TaskUpdate,
    TaskView,
)
from .store import AppError, TaskStore

DUE_SOON_HOURS = 24
SORT_FIELDS = ("created_at", "updated_at", "due_date", "priority", "status", "title")


# --- helpers ---------------------------------------------------------------
def is_open(task: Task) -> bool:
    return task.status in OPEN_STATUSES


def is_overdue(task: Task, now: datetime) -> bool:
    return is_open(task) and task.due_date is not None and task.due_date < now


def is_due_soon(task: Task, now: datetime, within_hours: int = DUE_SOON_HOURS) -> bool:
    return (
        is_open(task)
        and task.due_date is not None
        and now <= task.due_date <= now + timedelta(hours=within_hours)
    )


def to_view(task: Task, store: TaskStore, now: datetime) -> TaskView:
    assignee = store.get_assignee(task.assignee_id) if task.assignee_id else None
    return TaskView(
        **task.model_dump(),
        is_overdue=is_overdue(task, now),
        assignee=AssigneeSummary(id=assignee.id, full_name=assignee.full_name) if assignee else None,
        assignee_name=assignee.full_name if assignee else None,
    )


def _validation_error(field: str, message: str) -> AppError:
    return AppError(422, "VALIDATION_ERROR", "Validation failed", [{"field": field, "message": message}])


def _check_assignee(store: TaskStore, assignee_id: Optional[UUID]) -> None:
    if assignee_id is not None and store.get_assignee(assignee_id) is None:
        raise _validation_error("assignee_id", "Assignee not found")


def _check_dates(due_date: Optional[datetime], remind_at: Optional[datetime]) -> None:
    if due_date is not None and remind_at is not None and remind_at > due_date:
        raise _validation_error("remind_at", "Reminder must not be after the due date")


def _get_or_404(store: TaskStore, task_id: UUID) -> Task:
    task = store.get(task_id)
    if task is None:
        raise AppError(404, "TASK_NOT_FOUND", "Task not found")
    return task


# --- create / read / update / delete ----------------------------------------
def create_task(store: TaskStore, data: TaskCreate, now: datetime, created_by: Optional[UUID] = None) -> Task:
    _check_assignee(store, data.assignee_id)
    _check_dates(data.due_date, data.remind_at)
    task = Task(
        id=uuid4(),
        **data.model_dump(),
        completed_at=now if data.status == "done" else None,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    return store.add(task)


def get_task(store: TaskStore, task_id: UUID) -> Task:
    return _get_or_404(store, task_id)


def update_task(store: TaskStore, task_id: UUID, data: TaskUpdate, now: datetime) -> Task:
    task = _get_or_404(store, task_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise AppError(400, "NO_FIELDS_TO_UPDATE", "Provide at least one field to update")

    # title and status can be left out, but not set to "nothing"
    for required in ("title", "status", "priority"):
        if required in changes and changes[required] is None:
            raise _validation_error(required, "This field cannot be empty")

    updated = task.model_copy(update=changes)
    _check_assignee(store, updated.assignee_id)
    _check_dates(updated.due_date, updated.remind_at)

    # Completing a task stamps the time; re-opening it clears the stamp.
    if updated.status == "done" and task.status != "done":
        updated.completed_at = now
    elif updated.status != "done":
        updated.completed_at = None

    updated.updated_at = now
    return store.save(updated)


def delete_task(store: TaskStore, task_id: UUID, now: datetime) -> None:
    task = _get_or_404(store, task_id)
    store.save(task.model_copy(update={"deleted_at": now, "updated_at": now}))


# --- list with filters, sort and pages --------------------------------------
def _sort_key(field: str):
    if field == "priority":
        return lambda t: PRIORITY_RANK[t.priority]
    return lambda t: getattr(t, field)


def list_tasks(store: TaskStore, filters: ListFilters, now: datetime) -> Tuple[List[Task], int]:
    tasks = store.all()

    if filters.status:
        tasks = [t for t in tasks if t.status in filters.status]
    if filters.priority:
        tasks = [t for t in tasks if t.priority in filters.priority]
    if filters.assignee_id:
        tasks = [t for t in tasks if t.assignee_id == filters.assignee_id]
    if filters.customer_id:
        tasks = [t for t in tasks if t.customer_id == filters.customer_id]
    if filters.due_before:
        tasks = [t for t in tasks if t.due_date and t.due_date <= filters.due_before]
    if filters.due_after:
        tasks = [t for t in tasks if t.due_date and t.due_date >= filters.due_after]
    if filters.overdue:
        tasks = [t for t in tasks if is_overdue(t, now)]
    if filters.search:
        needle = filters.search.strip().lower()
        tasks = [
            t for t in tasks
            if needle in t.title.lower() or needle in (t.description or "").lower()
        ]

    descending = filters.sort.startswith("-")
    field = filters.sort.lstrip("-")
    if field not in SORT_FIELDS:
        raise _validation_error("sort", "Sort must be one of: " + ", ".join(SORT_FIELDS))

    key = _sort_key(field)
    # Tasks without a value for the sort field (e.g. no due date) always go last.
    with_value = [t for t in tasks if getattr(t, field) is not None]
    without_value = [t for t in tasks if getattr(t, field) is None]
    with_value.sort(key=key, reverse=descending)
    tasks = with_value + without_value

    total = len(tasks)
    start = (filters.page - 1) * filters.limit
    return tasks[start:start + filters.limit], total


def total_pages(total: int, limit: int) -> int:
    return max(1, math.ceil(total / limit)) if total else 0


# --- reminders and progress -------------------------------------------------
def get_reminders(store: TaskStore, now: datetime, within_hours: int = DUE_SOON_HOURS) -> List[Reminder]:
    """Open tasks that need attention now.

    * overdue   - the due date has passed
    * due_soon  - due within the next ``within_hours`` hours
    * reminder  - the task's own ``remind_at`` time has passed (and it is not
                  already overdue or due soon, so nobody sees it twice)

    Most urgent first: overdue (oldest deadline first), then due soon, then reminders.
    """
    reminders: List[Reminder] = []
    for task in store.all():
        if not is_open(task):
            continue
        view = to_view(task, store, now)
        if is_overdue(task, now):
            hours = int((now - task.due_date).total_seconds() // 3600)
            reminders.append(Reminder(reminder_type="overdue", task=view,
                                      message=f"Overdue by {_human(hours)}"))
        elif is_due_soon(task, now, within_hours):
            hours = int((task.due_date - now).total_seconds() // 3600)
            reminders.append(Reminder(reminder_type="due_soon", task=view,
                                      message=f"Due in {_human(hours)}" if hours else "Due within the hour"))
        elif task.remind_at is not None and task.remind_at <= now:
            reminders.append(Reminder(reminder_type="reminder", task=view,
                                      message="Reminder time reached"))

    order = {"overdue": 0, "due_soon": 1, "reminder": 2}
    reminders.sort(key=lambda r: (
        order[r.reminder_type],
        r.task.due_date or r.task.remind_at or now,
    ))
    return reminders


def _human(hours: int) -> str:
    if hours < 1:
        return "less than an hour"
    if hours < 48:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{hours // 24} days"


def progress_summary(store: TaskStore, now: datetime, assignee_id: Optional[UUID] = None,
                     within_hours: int = DUE_SOON_HOURS) -> ProgressSummary:
    """Numbers for the progress view.

    ``completed_percent`` = done / (all tasks except cancelled). Cancelled tasks
    are left out so cancelling a task does not make progress look worse.
    """
    tasks = store.all()
    if assignee_id is not None:
        tasks = [t for t in tasks if t.assignee_id == assignee_id]

    by_status = {s: 0 for s in ("todo", "in_progress", "done", "cancelled")}
    open_by_priority = {p: 0 for p in ("urgent", "high", "medium", "low")}
    for t in tasks:
        by_status[t.status] += 1
        if is_open(t):
            open_by_priority[t.priority] += 1

    counted = len(tasks) - by_status["cancelled"]
    percent = round(100 * by_status["done"] / counted, 1) if counted else 0.0
    return ProgressSummary(
        total=len(tasks),
        by_status=by_status,
        open_by_priority=open_by_priority,
        completed_percent=percent,
        overdue=sum(1 for t in tasks if is_overdue(t, now)),
        due_soon=sum(1 for t in tasks if is_due_soon(t, now, within_hours)),
    )
