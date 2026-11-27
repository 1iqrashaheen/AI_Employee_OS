"""Backend mode: use the shared backend (Hadeed's FastAPI + PostgreSQL) for the data.

Set ``TASK_BACKEND_URL`` (for example ``http://127.0.0.1:8000/api/v1``) and the task manager
stops using its own storage:

* Creating, reading, editing and deleting tasks, and signing in, are passed straight to the
  shared backend with the caller's own ``Authorization`` header. The backend's login, company
  separation, permissions and validation all apply; nothing is re-implemented here.
* The reminders, the progress view and the assignee list are this module's own features.
  The shared backend has no such endpoints, so they are worked out here from the backend's
  task list, using the same rules (``service.py``) as the standalone version.

Nothing is stored in this module in backend mode, and no password or token is kept by the server.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

from .schemas import Assignee, Task
from .store import AppError, TaskStore

PAGE_LIMIT = 100  # the shared backend allows at most 100 per page
MAX_PAGES = 50    # safety stop: 5,000 tasks is far beyond a demo


class BackendClient:
    """A small HTTP client for the shared backend."""

    def __init__(self, base_url: str, transport: Optional[httpx.AsyncBaseTransport] = None,
                 timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self._transport = transport
        self._timeout = timeout

    async def _send(self, method: str, path: str, *, authorization: Optional[str],
                    params=None, content: Optional[bytes] = None,
                    content_type: Optional[str] = None) -> Tuple[int, Dict[str, Any]]:
        headers = {}
        if authorization:
            headers["Authorization"] = authorization
        if content_type:
            headers["Content-Type"] = content_type
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self._timeout) as http:
                res = await http.request(method, self.base_url + path, params=params,
                                         content=content, headers=headers)
        except httpx.RequestError as exc:
            raise AppError(502, "BACKEND_UNAVAILABLE",
                           "The shared backend could not be reached") from exc
        try:
            body = res.json()
        except ValueError as exc:
            raise AppError(502, "BACKEND_BAD_RESPONSE",
                           "The shared backend sent a reply that is not JSON") from exc
        if not isinstance(body, dict):
            raise AppError(502, "BACKEND_BAD_RESPONSE", "The shared backend sent an unexpected reply")
        return res.status_code, body

    async def forward(self, request: Request, backend_path: str) -> JSONResponse:
        """Pass a request to the backend and return its answer unchanged (status and body)."""
        status, body = await self._send(
            request.method, backend_path,
            authorization=request.headers.get("authorization"),
            params=list(request.query_params.multi_items()),
            content=(await request.body()) or None,
            content_type=request.headers.get("content-type"),
        )
        return JSONResponse(status_code=status, content=body)

    async def get_data(self, path: str, authorization: Optional[str], params=None) -> Dict[str, Any]:
        """GET and return the body, turning a backend error into this module's error response."""
        status, body = await self._send("GET", path, authorization=authorization, params=params)
        if status >= 400:
            raise AppError(status, body.get("code", "BACKEND_ERROR"),
                           body.get("message", "The shared backend refused the request"),
                           body.get("errors") or [])
        return body

    async def get_all_pages(self, path: str, authorization: Optional[str]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            body = await self.get_data(path, authorization, {"page": page, "limit": PAGE_LIMIT})
            rows.extend(body.get("data") or [])
            if page >= (body.get("meta") or {}).get("total_pages", 1):
                return rows
        raise AppError(502, "BACKEND_TOO_MANY_PAGES", "There are more tasks than this module can read")


# --- turning the backend's answers into this module's objects ---------------------
def _aware(value: Optional[datetime]) -> Optional[datetime]:
    """Some databases return dates without a zone; the backend stores UTC, so say so."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def task_from_backend(row: Dict[str, Any]) -> Task:
    task = Task.model_validate(row)  # extra fields (company_id, customer, ...) are ignored
    task.due_date = _aware(task.due_date)
    task.remind_at = _aware(task.remind_at)
    task.completed_at = _aware(task.completed_at)
    return task


def assignee_from_backend(row: Dict[str, Any]) -> Assignee:
    return Assignee(id=row["id"], full_name=row["full_name"], role=row.get("role"))


async def load_store(client: BackendClient, authorization: Optional[str]) -> TaskStore:
    """Read the caller's tasks and people from the backend into a short-lived in-memory store,
    so ``service.get_reminders`` and ``service.progress_summary`` can run on them."""
    task_rows = await client.get_all_pages("/tasks", authorization)
    people = await client.get_all_pages("/users/directory", authorization)

    assignees = {str(p["id"]): assignee_from_backend(p) for p in people}
    store = TaskStore(assignees=[])
    for row in task_rows:
        store.add(task_from_backend(row))
        # keep the name of an assignee who is no longer in the directory (for example deactivated)
        person = row.get("assignee")
        if person and str(person["id"]) not in assignees:
            assignees[str(person["id"])] = assignee_from_backend(person)
    store.assignees = list(assignees.values())
    return store
