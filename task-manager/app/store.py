"""Where tasks are kept.

For now tasks live in memory, with sample data, so this module can be built and
tested on its own (the team plan says to start with sample tasks and connect to
shared storage later). Everything else in the module only talks to the small
``TaskStore`` interface below, so the final step is to write a second class with
the same methods that reads and writes Hadeed's ``tasks`` table.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from .schemas import Assignee, Task


class AppError(Exception):
    """An error that is turned into the standard error response (see main.py)."""

    def __init__(self, status_code: int, code: str, message: str, errors=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.errors = errors or []


# Sample people. Stand-ins for the shared `users` table until it is connected.
SAMPLE_ASSIGNEES: List[Assignee] = [
    Assignee(id=UUID("00000000-0000-4000-8000-000000000001"), full_name="Ali Khan", role="admin"),
    Assignee(id=UUID("00000000-0000-4000-8000-000000000002"), full_name="Sara Ahmed", role="manager"),
    Assignee(id=UUID("00000000-0000-4000-8000-000000000003"), full_name="Aamna Hameed", role="member"),
    Assignee(id=UUID("00000000-0000-4000-8000-000000000004"), full_name="Hamza Raza", role="member"),
]


class TaskStore:
    """Task storage in memory. Deleted tasks are kept but marked (soft delete)."""

    def __init__(self, assignees: Optional[List[Assignee]] = None):
        self._tasks: Dict[UUID, Task] = {}
        self.assignees: List[Assignee] = list(assignees if assignees is not None else SAMPLE_ASSIGNEES)

    # --- assignees ---------------------------------------------------------
    def get_assignee(self, assignee_id: UUID) -> Optional[Assignee]:
        return next((a for a in self.assignees if a.id == assignee_id), None)

    # --- tasks -------------------------------------------------------------
    def all(self) -> List[Task]:
        """All tasks that have not been deleted."""
        return [t for t in self._tasks.values() if t.deleted_at is None]

    def get(self, task_id: UUID) -> Optional[Task]:
        task = self._tasks.get(task_id)
        return task if task is not None and task.deleted_at is None else None

    def add(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task

    def save(self, task: Task) -> Task:
        self._tasks[task.id] = task
        return task


class JsonFileTaskStore(TaskStore):
    """Same as ``TaskStore`` but saved to a JSON file, so tasks survive a restart.

    Meant for demos before the shared database is connected. The file is loaded
    when the store is created and rewritten after every change. A write failure
    raises an error (it is never ignored), and the file is replaced in one step so
    a crash cannot leave it half-written.
    """

    def __init__(self, path, assignees: Optional[List[Assignee]] = None):
        super().__init__(assignees)
        self.path = Path(path)
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            rows = json.loads(self.path.read_text(encoding="utf-8"))
            for row in rows:
                task = Task.model_validate(row)
                task.deleted_at = _parse_dt(row.get("deleted_at"))
                self._tasks[task.id] = task
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError(f"Could not read task file {self.path}: {exc}") from exc

    def _write(self) -> None:
        rows = []
        for task in self._tasks.values():
            row = task.model_dump(mode="json")  # deleted_at is left out of normal output
            row["deleted_at"] = task.deleted_at.isoformat() if task.deleted_at else None
            rows.append(row)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            raise RuntimeError(f"Could not write task file {self.path}: {exc}") from exc

    def add(self, task: Task) -> Task:
        super().add(task)
        self._write()
        return task

    def save(self, task: Task) -> Task:
        super().save(task)
        self._write()
        return task


def _parse_dt(value) -> Optional[datetime]:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def seed_sample_data(store: TaskStore, now: datetime) -> None:
    """Fill the store with example tasks that show every state the UI can display.

    Dates are relative to ``now`` so there is always something overdue and
    something due soon, whenever the app is started.
    """
    ali, sara, aamna, hamza = (a.id for a in store.assignees)
    hours = lambda h: now + timedelta(hours=h)  # noqa: E731

    samples = [
        # (title, description, status, priority, due, remind, assignee)
        ("Send revised quotation to John", "25 laptops, include the 10% discount.",
         "todo", "urgent", hours(-26), hours(-30), sara),
        ("Reply to BigCorp support email", None,
         "in_progress", "high", hours(-3), None, aamna),
        ("Prepare monthly sales report", "Use the sales and expense numbers from the reports module.",
         "in_progress", "high", hours(6), hours(4), ali),
        ("Follow up with John about quotation", "He has not replied in three days.",
         "todo", "medium", hours(20), hours(18), hamza),
        ("Book Friday 3 PM meeting with John", None,
         "todo", "medium", hours(70), hours(60), aamna),
        ("Update customer stage in the CRM", None,
         "todo", "low", hours(120), None, hamza),
        ("Review the invoice template", "Check tax and due-date fields.",
         "done", "medium", hours(-48), None, ali),
        ("Collect sample documents for testing", None,
         "done", "low", hours(-10), None, aamna),
        ("Old vendor call", "No longer needed.",
         "cancelled", "low", hours(-72), None, sara),
        ("Write the task manager README", "Run steps and test evidence.",
         "todo", "medium", None, hours(2), aamna),
    ]
    for i, (title, description, status, priority, due, remind, assignee) in enumerate(samples):
        created = now - timedelta(days=3, hours=-i)
        store.add(Task(
            id=uuid4(), title=title, description=description, status=status, priority=priority,
            due_date=due, remind_at=remind,
            completed_at=(due or now) if status == "done" else None,
            assignee_id=assignee, source="manual", created_by=ali,
            created_at=created, updated_at=created,
        ))
