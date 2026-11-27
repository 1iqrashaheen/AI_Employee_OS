"""Backend mode: the task manager uses the shared backend for its data.

The shared backend is replaced by a fake that answers in the same shapes as Hadeed's
real API (``ai-employee-os-backend``, branch feature/authentication), so these tests need
no database. ``docs/test-results.md`` also records a run against the real backend.
"""
import json
import math
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.backend import BackendClient
from app.main import create_app

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
TOKEN = "good-token"
COMPANY = "11111111-1111-4111-8111-111111111111"
ALI = {"id": "00000000-0000-4000-8000-000000000001", "full_name": "Ali Khan"}
SARA = {"id": "00000000-0000-4000-8000-000000000002", "full_name": "Sara Ahmed"}
GONE = {"id": "00000000-0000-4000-8000-000000000009", "full_name": "Former Colleague"}  # not in the directory
PAGE_SIZE = 2  # tiny pages, so reading "all tasks" has to walk several pages


def hours(h):
    return (NOW + timedelta(hours=h)).isoformat().replace("+00:00", "Z")


def row(n, title, status="todo", priority="medium", due=None, remind=None, assignee=None):
    """A task as the real backend returns it (TaskOut)."""
    return {
        "id": f"22222222-2222-4222-8222-{n:012d}", "company_id": COMPANY, "title": title,
        "description": None, "status": status, "priority": priority, "due_date": due,
        "remind_at": remind, "completed_at": hours(-1) if status == "done" else None,
        "assignee_id": assignee["id"] if assignee else None, "assignee": assignee,
        "customer_id": None, "customer": None, "record_id": None, "source": "manual",
        "created_by": ALI["id"], "created_at": hours(-72), "updated_at": hours(-72),
        "is_overdue": False,
    }


def error(status, code, message, errors=None):
    return httpx.Response(status, json={"success": False, "message": message, "code": code, "errors": errors})


class FakeBackend:
    """Remembers every request it receives and answers like the real backend."""

    def __init__(self, tasks):
        self.tasks = list(tasks)
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path.removeprefix("/api/v1")

        if path == "/auth/login":
            credentials = json.loads(request.content)
            if credentials.get("password") != "Secret123!":
                return error(401, "INVALID_CREDENTIALS", "Incorrect email or password")
            return httpx.Response(200, json={"success": True, "message": "Login successful",
                                             "data": {"access_token": TOKEN, "user": {**ALI, "role": "admin"}}})
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return error(401, "AUTH_REQUIRED", "Authentication required")

        if path == "/users/directory":
            return self._page(request, [ALI, SARA])
        if path == "/tasks" and request.method == "GET":
            return self._page(request, self.tasks)
        if path == "/tasks" and request.method == "POST":
            body = json.loads(request.content)
            if not body.get("title"):
                return error(422, "VALIDATION_ERROR", "Validation failed",
                             [{"field": "title", "message": "Field required"}])
            created = row(len(self.tasks) + 1, body["title"], priority=body.get("priority", "medium"))
            self.tasks.append(created)
            return httpx.Response(201, json={"success": True, "message": "Task created successfully", "data": created})
        if path.startswith("/tasks/"):
            found = next((t for t in self.tasks if t["id"] == path.split("/")[-1]), None)
            if found is None:
                return error(404, "TASK_NOT_FOUND", "Task not found")
            if request.method == "DELETE":
                return httpx.Response(200, json={"success": True, "message": "Task deleted", "data": None})
            if request.method == "PATCH":
                found.update(json.loads(request.content))
            return httpx.Response(200, json={"success": True, "message": "OK", "data": found})
        return error(404, "NOT_FOUND", "Not found")

    @staticmethod
    def _page(request, items):
        page = int(request.url.params.get("page", 1))
        pages = max(1, math.ceil(len(items) / PAGE_SIZE))
        chunk = items[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
        return httpx.Response(200, json={"success": True, "message": "OK", "data": chunk,
                                         "meta": {"page": page, "limit": PAGE_SIZE, "total": len(items),
                                                  "total_pages": pages}})


def make_client(backend):
    transport = httpx.MockTransport(backend)
    app = create_app(now_fn=lambda: NOW, backend_client=BackendClient("http://backend.test/api/v1", transport=transport))
    return TestClient(app)


AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture()
def backend():
    return FakeBackend([
        row(1, "Overdue quotation", priority="urgent", due=hours(-26), assignee=SARA),
        row(2, "Due this afternoon", priority="high", due=hours(6), assignee=ALI),
        row(3, "Reminder only", due=hours(100), remind=hours(-2)),
        row(4, "Finished", status="done", due=hours(-48), assignee=GONE),
        row(5, "Dropped", status="cancelled"),
    ])


@pytest.fixture()
def client(backend):
    return make_client(backend)


def test_health_says_which_mode(client):
    assert client.get("/api/v1/health").json()["data"]["mode"] == "backend"
    standalone = TestClient(create_app(now_fn=lambda: NOW))
    assert standalone.get("/api/v1/health").json()["data"]["mode"] == "standalone"


# --- sign in and the token --------------------------------------------------------------
def test_login_is_passed_to_the_backend(client, backend):
    res = client.post("/api/v1/auth/login", json={"email": "ali@acme.com", "password": "Secret123!"})
    assert res.status_code == 200 and res.json()["data"]["access_token"] == TOKEN
    assert json.loads(backend.requests[0].content) == {"email": "ali@acme.com", "password": "Secret123!"}


def test_wrong_password_error_is_passed_through_unchanged(client):
    res = client.post("/api/v1/auth/login", json={"email": "ali@acme.com", "password": "nope"})
    assert res.status_code == 401
    assert res.json()["code"] == "INVALID_CREDENTIALS" and res.json()["success"] is False


@pytest.mark.parametrize("path", ["/tasks", "/tasks/reminders", "/tasks/progress", "/assignees"])
def test_every_data_route_needs_a_login(client, path):
    res = client.get("/api/v1" + path)
    assert res.status_code == 401 and res.json()["code"] == "AUTH_REQUIRED"


def test_only_the_callers_token_is_passed_on(client, backend):
    client.get("/api/v1/tasks", headers={**AUTH, "Cookie": "session=secret", "X-Other": "1"})
    sent = backend.requests[-1]
    assert sent.headers["authorization"] == f"Bearer {TOKEN}"
    assert "cookie" not in sent.headers and "x-other" not in sent.headers


# --- create / read / edit / delete go to the backend -------------------------------------
def test_list_passes_filters_including_repeated_ones(client, backend):
    res = client.get("/api/v1/tasks?status=todo&status=in_progress&search=quote&sort=due_date&page=1&limit=2",
                     headers=AUTH)
    assert res.status_code == 200 and res.json()["meta"]["total"] == 5
    assert dict(backend.requests[-1].url.params.multi_items()) | {} == {
        "status": "in_progress", "search": "quote", "sort": "due_date", "page": "1", "limit": "2"}
    assert backend.requests[-1].url.params.get_list("status") == ["todo", "in_progress"]


def test_create_goes_to_the_backend_and_returns_its_answer(client, backend):
    res = client.post("/api/v1/tasks", json={"title": "Call John", "priority": "high"}, headers=AUTH)
    assert res.status_code == 201 and res.json()["data"]["title"] == "Call John"
    assert json.loads(backend.requests[-1].content) == {"title": "Call John", "priority": "high"}
    assert len(backend.tasks) == 6


def test_backend_validation_errors_reach_the_page_unchanged(client):
    res = client.post("/api/v1/tasks", json={"title": ""}, headers=AUTH)
    assert res.status_code == 422
    assert res.json()["errors"] == [{"field": "title", "message": "Field required"}]


def test_get_edit_and_delete_one_task(client, backend):
    task_id = backend.tasks[0]["id"]
    assert client.get(f"/api/v1/tasks/{task_id}", headers=AUTH).json()["data"]["title"] == "Overdue quotation"
    patched = client.patch(f"/api/v1/tasks/{task_id}", json={"status": "done"}, headers=AUTH)
    assert patched.json()["data"]["status"] == "done"
    assert client.delete(f"/api/v1/tasks/{task_id}", headers=AUTH).json()["message"] == "Task deleted"
    assert [r.method for r in backend.requests] == ["GET", "PATCH", "DELETE"]


def test_missing_task_error_is_passed_through(client):
    res = client.get("/api/v1/tasks/22222222-2222-4222-8222-999999999999", headers=AUTH)
    assert res.status_code == 404 and res.json()["code"] == "TASK_NOT_FOUND"


def test_a_bad_task_id_never_reaches_the_backend(client, backend):
    res = client.get("/api/v1/tasks/..%2Fusers", headers=AUTH)
    assert res.status_code in (404, 422)
    assert backend.requests == []


# --- this module's own features, worked out from the backend's tasks ------------------
def test_reminders_are_worked_out_from_all_pages(client, backend):
    res = client.get("/api/v1/tasks/reminders", headers=AUTH)
    assert res.status_code == 200
    got = [(r["reminder_type"], r["task"]["title"]) for r in res.json()["data"]]
    assert got == [("overdue", "Overdue quotation"), ("due_soon", "Due this afternoon"),
                   ("reminder", "Reminder only")]
    task_calls = [r for r in backend.requests if r.url.path.endswith("/tasks")]
    assert len(task_calls) == 3  # 5 tasks, 2 per page: pages 1, 2 and 3 were all read


def test_reminders_show_assignee_names_from_the_backend(client):
    data = client.get("/api/v1/tasks/reminders", headers=AUTH).json()["data"]
    assert data[0]["task"]["assignee_name"] == "Sara Ahmed"
    assert data[0]["task"]["assignee"] == SARA


def test_progress_is_worked_out_from_the_backend_tasks(client):
    data = client.get("/api/v1/tasks/progress", headers=AUTH).json()["data"]
    assert data["by_status"] == {"todo": 3, "in_progress": 0, "done": 1, "cancelled": 1}
    assert data["completed_percent"] == 25.0  # 1 done of 4 (the cancelled one is left out)
    assert data["overdue"] == 1 and data["due_soon"] == 1


def test_progress_for_one_person(client):
    data = client.get(f"/api/v1/tasks/progress?assignee_id={ALI['id']}", headers=AUTH).json()["data"]
    assert data["total"] == 1


def test_assignees_are_the_backends_directory(client):
    names = [a["full_name"] for a in client.get("/api/v1/assignees", headers=AUTH).json()["data"]]
    assert names == ["Ali Khan", "Sara Ahmed", "Former Colleague"]  # the last one is only on a task


def test_dates_without_a_zone_from_the_backend_are_read_as_utc(backend):
    backend.tasks = [row(1, "Naive date", due="2026-11-18T10:00:00")]  # some databases drop the zone
    res = make_client(backend).get("/api/v1/tasks/reminders", headers=AUTH)
    assert res.status_code == 200 and res.json()["data"][0]["reminder_type"] == "overdue"


# --- when the backend is not working --------------------------------------------------
def test_backend_down_gives_a_clear_error():
    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    client = make_client(refuse)
    for path in ("/tasks", "/tasks/reminders"):
        res = client.get("/api/v1" + path, headers=AUTH)
        assert res.status_code == 502 and res.json()["code"] == "BACKEND_UNAVAILABLE"
        assert res.json()["success"] is False


def test_a_reply_that_is_not_json_gives_a_clear_error():
    client = make_client(lambda request: httpx.Response(200, text="<html>proxy error</html>"))
    res = client.get("/api/v1/tasks", headers=AUTH)
    assert res.status_code == 502 and res.json()["code"] == "BACKEND_BAD_RESPONSE"
