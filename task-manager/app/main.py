"""Task Manager and Reminders: standalone FastAPI app.

Run:   uvicorn app.main:app --reload --port 8001
Docs:  http://localhost:8001/docs     UI: http://localhost:8001/

Responses use the team's standard shape (success / message / data / meta) and
errors use (success / message / code / errors), as in the backend design doc.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import service
from .schemas import ListFilters, TaskCreate, TaskUpdate, TaskPriority, TaskStatus
from .store import AppError, TaskStore, seed_sample_data

STATIC_DIR = Path(__file__).parent / "static"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ok(message: str, data, meta: Optional[dict] = None) -> dict:
    body = {"success": True, "message": message, "data": data}
    if meta is not None:
        body["meta"] = meta
    return body


def _error(status: int, code: str, message: str, errors=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"success": False, "message": message, "code": code, "errors": errors or []},
    )


def create_app(
    store: Optional[TaskStore] = None,
    now_fn: Callable[[], datetime] = _utcnow,
    seed: bool = False,
) -> FastAPI:
    """Build the app. Tests pass their own store and clock; seed=True adds sample tasks."""
    app = FastAPI(title="AI Employee OS - Task Manager", version="0.1.0")
    app.state.store = store or TaskStore()
    app.state.now_fn = now_fn
    if seed:
        seed_sample_data(app.state.store, now_fn())

    def get_store(request: Request) -> TaskStore:
        return request.app.state.store

    def get_now(request: Request) -> datetime:
        return request.app.state.now_fn()

    # --- error handling: every error leaves in the same shape ----------------
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return _error(exc.status_code, exc.code, exc.message, exc.errors)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path")),
                "message": e["msg"].replace("Value error, ", ""),
            }
            for e in exc.errors()
        ]
        return _error(422, "VALIDATION_ERROR", "Validation failed", errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "BAD_REQUEST"
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        # details go to the server log only, never to the client
        import logging
        logging.getLogger("task_manager").exception("Unhandled error", exc_info=exc)
        return _error(500, "INTERNAL_ERROR", "Something went wrong")

    # --- routes ---------------------------------------------------------------
    api = "/api/v1"

    @app.get(f"{api}/health", tags=["Health"])
    def health():
        return _ok("OK", {"status": "healthy"})

    @app.get(f"{api}/assignees", tags=["Tasks"])
    def assignees(store: TaskStore = Depends(get_store)):
        """People a task can be assigned to (sample users until the shared users API is connected)."""
        return _ok("OK", [a.model_dump(mode="json") for a in store.assignees])

    @app.get(f"{api}/tasks", tags=["Tasks"])
    def list_tasks(
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        assignee_id: Optional[UUID] = None,
        customer_id: Optional[UUID] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
        overdue: bool = False,
        search: Optional[str] = None,
        sort: str = "-created_at",
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        store: TaskStore = Depends(get_store),
        now: datetime = Depends(get_now),
    ):
        filters = ListFilters(
            status=status, priority=priority, assignee_id=assignee_id, customer_id=customer_id,
            due_before=due_before, due_after=due_after, overdue=overdue, search=search,
            sort=sort, page=page, limit=limit,
        )
        tasks, total = service.list_tasks(store, filters, now)
        data = [service.to_view(t, store, now).model_dump(mode="json") for t in tasks]
        meta = {"page": page, "limit": limit, "total": total,
                "total_pages": service.total_pages(total, limit)}
        return _ok("OK", data, meta)

    # fixed paths must come before /tasks/{task_id}
    @app.get(f"{api}/tasks/reminders", tags=["Reminders"])
    def reminders(
        within_hours: int = Query(service.DUE_SOON_HOURS, ge=1, le=24 * 30),
        store: TaskStore = Depends(get_store),
        now: datetime = Depends(get_now),
    ):
        """Open tasks that are overdue, due soon, or whose reminder time has passed."""
        items = service.get_reminders(store, now, within_hours)
        return _ok("OK", [r.model_dump(mode="json") for r in items], {"total": len(items)})

    @app.get(f"{api}/tasks/progress", tags=["Reminders"])
    def progress(
        assignee_id: Optional[UUID] = None,
        store: TaskStore = Depends(get_store),
        now: datetime = Depends(get_now),
    ):
        """Counts and completion percentage for the progress view."""
        return _ok("OK", service.progress_summary(store, now, assignee_id).model_dump(mode="json"))

    @app.post(f"{api}/tasks", status_code=201, tags=["Tasks"])
    def create_task(
        body: TaskCreate,
        store: TaskStore = Depends(get_store),
        now: datetime = Depends(get_now),
    ):
        task = service.create_task(store, body, now)
        return _ok("Task created successfully", service.to_view(task, store, now).model_dump(mode="json"))

    @app.get(api + "/tasks/{task_id}", tags=["Tasks"])
    def get_task(task_id: UUID, store: TaskStore = Depends(get_store), now: datetime = Depends(get_now)):
        task = service.get_task(store, task_id)
        return _ok("OK", service.to_view(task, store, now).model_dump(mode="json"))

    @app.patch(api + "/tasks/{task_id}", tags=["Tasks"])
    def update_task(
        task_id: UUID,
        body: TaskUpdate,
        store: TaskStore = Depends(get_store),
        now: datetime = Depends(get_now),
    ):
        """Partial update. Setting status to `done` stamps `completed_at` automatically."""
        task = service.update_task(store, task_id, body, now)
        return _ok("Task updated successfully", service.to_view(task, store, now).model_dump(mode="json"))

    @app.delete(api + "/tasks/{task_id}", tags=["Tasks"])
    def delete_task(task_id: UUID, store: TaskStore = Depends(get_store), now: datetime = Depends(get_now)):
        service.delete_task(store, task_id, now)
        return _ok("Task deleted successfully", None)

    # --- the simple web page --------------------------------------------------
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app


# `uvicorn app.main:app` starts with sample tasks unless TASK_MANAGER_SEED=0
app = create_app(seed=os.getenv("TASK_MANAGER_SEED", "1") == "1")
