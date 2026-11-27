"""Task Manager and Reminders: standalone FastAPI app.

Run:   uvicorn app.main:app --reload --port 8001
Docs:  http://localhost:8001/docs     UI: http://localhost:8001/

Responses use the team's standard shape (success / message / data / meta) and
errors use (success / message / code / errors), as in the backend design doc.

Two modes:
* standalone (default): tasks are kept here (memory, or a JSON file), with sample data.
* backend mode (``TASK_BACKEND_URL`` set): the shared backend holds the data; see backend.py.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import backend, service
from .schemas import ListFilters, TaskCreate, TaskUpdate, TaskPriority, TaskStatus
from .backend import BackendClient
from .store import AppError, JsonFileTaskStore, TaskStore, seed_sample_data

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
    backend_client: Optional[BackendClient] = None,
) -> FastAPI:
    """Build the app. Tests pass their own store and clock; seed=True adds sample tasks.

    Pass ``backend_client`` to use the shared backend instead of local storage."""
    app = FastAPI(title="AI Employee OS - Task Manager", version="0.1.0")
    app.state.store = store or TaskStore()
    app.state.now_fn = now_fn
    if seed and backend_client is None and not app.state.store.all():  # never add samples on top of saved tasks
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
        """`mode` tells the web page whether it must show the sign-in form."""
        return _ok("OK", {"status": "healthy", "mode": "standalone" if backend_client is None else "backend"})

    if backend_client is not None:
        _add_backend_routes(app, api, backend_client, get_now)
        _add_web_page(app)
        return app

    @app.get(f"{api}/assignees", tags=["Tasks"])
    def assignees(store: TaskStore = Depends(get_store)):
        """People a task can be assigned to (sample users until the shared users API is connected)."""
        return _ok("OK", [a.model_dump(mode="json") for a in store.assignees])

    @app.get(f"{api}/tasks", tags=["Tasks"])
    def list_tasks(
        status: Optional[List[TaskStatus]] = Query(None, description="Repeat for several: ?status=todo&status=in_progress"),
        priority: Optional[List[TaskPriority]] = Query(None, description="Repeat for several"),
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

    _add_web_page(app)
    return app


def _add_web_page(app: FastAPI) -> None:
    """The simple web page (the same page in both modes)."""
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")


def _add_backend_routes(app: FastAPI, api: str, client: BackendClient, get_now) -> None:
    """Routes for backend mode. The caller's own token is passed on; nothing is stored here."""

    def auth_of(request: Request) -> Optional[str]:
        return request.headers.get("authorization")

    # sign in: passed on unchanged, so the web page can use the shared login
    @app.post(f"{api}/auth/login", tags=["Backend login"])
    async def login(request: Request):
        return await client.forward(request, "/auth/login")

    @app.get(f"{api}/auth/me", tags=["Backend login"])
    async def me(request: Request):
        return await client.forward(request, "/auth/me")

    # this module's own features, worked out from the backend's tasks
    @app.get(f"{api}/assignees", tags=["Tasks"])
    async def assignees(request: Request):
        """People a task can be assigned to: the shared backend's active users."""
        store = await backend.load_store(client, auth_of(request))
        return _ok("OK", [a.model_dump(mode="json") for a in store.assignees])

    @app.get(f"{api}/tasks/reminders", tags=["Reminders"])
    async def reminders(request: Request, within_hours: int = Query(service.DUE_SOON_HOURS, ge=1, le=24 * 30),
                        now: datetime = Depends(get_now)):
        store = await backend.load_store(client, auth_of(request))
        items = service.get_reminders(store, now, within_hours)
        return _ok("OK", [r.model_dump(mode="json") for r in items], {"total": len(items)})

    @app.get(f"{api}/tasks/progress", tags=["Reminders"])
    async def progress(request: Request, assignee_id: Optional[UUID] = None,
                       now: datetime = Depends(get_now)):
        store = await backend.load_store(client, auth_of(request))
        return _ok("OK", service.progress_summary(store, now, assignee_id).model_dump(mode="json"))

    # create, read, edit, delete: the shared backend does the work and the checking
    @app.get(f"{api}/tasks", tags=["Tasks"])
    async def list_tasks(request: Request):
        return await client.forward(request, "/tasks")

    @app.post(f"{api}/tasks", status_code=201, tags=["Tasks"])
    async def create_task(request: Request):
        return await client.forward(request, "/tasks")

    @app.get(api + "/tasks/{task_id}", tags=["Tasks"])
    async def get_task(request: Request, task_id: UUID):
        return await client.forward(request, f"/tasks/{task_id}")

    @app.patch(api + "/tasks/{task_id}", tags=["Tasks"])
    async def update_task(request: Request, task_id: UUID):
        return await client.forward(request, f"/tasks/{task_id}")

    @app.delete(api + "/tasks/{task_id}", tags=["Tasks"])
    async def delete_task(request: Request, task_id: UUID):
        return await client.forward(request, f"/tasks/{task_id}")


# `uvicorn app.main:app` starts with sample tasks unless TASK_MANAGER_SEED=0.
# Set TASK_MANAGER_FILE=tasks.json to keep tasks between restarts.
# Set TASK_BACKEND_URL=http://127.0.0.1:8000/api/v1 to use the shared backend instead.
_data_file = os.getenv("TASK_MANAGER_FILE")
_backend_url = os.getenv("TASK_BACKEND_URL")
app = create_app(
    store=JsonFileTaskStore(_data_file) if _data_file else None,
    seed=os.getenv("TASK_MANAGER_SEED", "1") == "1",
    backend_client=BackendClient(_backend_url) if _backend_url else None,
)
