"""API tests for create / edit / assign / complete / delete / filter / paging.

Every test uses a fresh empty store and a fixed clock (NOW), so results never
depend on when the tests are run.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import SAMPLE_ASSIGNEES, TaskStore

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
ALI, SARA = SAMPLE_ASSIGNEES[0].id, SAMPLE_ASSIGNEES[1].id


def iso(hours=0):
    return (NOW + timedelta(hours=hours)).isoformat()


@pytest.fixture()
def client():
    return TestClient(create_app(store=TaskStore(), now_fn=lambda: NOW, seed=False))


def make(client, **fields):
    body = {"title": "Write report", **fields}
    res = client.post("/api/v1/tasks", json=body)
    assert res.status_code == 201, res.text
    return res.json()["data"]


# --- create ------------------------------------------------------------------
def test_create_task_uses_defaults(client):
    res = client.post("/api/v1/tasks", json={"title": "  Call John  "})
    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True and body["message"] == "Task created successfully"
    task = body["data"]
    assert task["title"] == "Call John"  # trimmed
    assert (task["status"], task["priority"], task["source"]) == ("todo", "medium", "manual")
    assert task["completed_at"] is None and task["is_overdue"] is False


def test_create_with_all_fields_and_assignee_name(client):
    task = make(client, description="d", priority="urgent", assignee_id=str(SARA),
                due_date=iso(48), remind_at=iso(24))
    assert task["assignee_name"] == "Sara Ahmed"
    assert task["priority"] == "urgent"


@pytest.mark.parametrize("body, field", [
    ({}, "title"),
    ({"title": "   "}, "title"),
    ({"title": "x" * 201}, "title"),
    ({"title": "a", "priority": "critical"}, "priority"),
    ({"title": "a", "status": "finished"}, "status"),
    ({"title": "a", "due_date": "not-a-date"}, "due_date"),
])
def test_create_rejects_bad_input(client, body, field):
    res = client.post("/api/v1/tasks", json=body)
    assert res.status_code == 422
    err = res.json()
    assert err["success"] is False and err["code"] == "VALIDATION_ERROR"
    assert field in [e["field"] for e in err["errors"]]


def test_reminder_after_due_date_is_rejected(client):
    res = client.post("/api/v1/tasks", json={"title": "a", "due_date": iso(1), "remind_at": iso(2)})
    assert res.status_code == 422
    assert res.json()["errors"][0]["field"] == "remind_at"


def test_unknown_assignee_is_rejected(client):
    res = client.post("/api/v1/tasks", json={"title": "a", "assignee_id": "11111111-1111-4111-8111-111111111111"})
    assert res.status_code == 422
    assert res.json()["errors"][0] == {"field": "assignee_id", "message": "Assignee not found"}


def test_naive_dates_are_treated_as_utc(client):
    task = make(client, due_date="2026-11-20T09:00:00")
    assert task["due_date"].startswith("2026-11-20T09:00:00")


# --- read ----------------------------------------------------------------------
def test_get_task_and_404s(client):
    task = make(client)
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["data"]["id"] == task["id"]
    missing = client.get("/api/v1/tasks/22222222-2222-4222-8222-222222222222")
    assert missing.status_code == 404 and missing.json()["code"] == "NOT_FOUND"
    assert client.get("/api/v1/tasks/not-a-uuid").status_code == 422


# --- edit / assign / complete -------------------------------------------------
def test_edit_assign_and_change_priority(client):
    task = make(client)
    res = client.patch(f"/api/v1/tasks/{task['id']}",
                       json={"title": "New title", "priority": "high", "assignee_id": str(ALI)})
    assert res.status_code == 200
    data = res.json()["data"]
    assert (data["title"], data["priority"], data["assignee_name"]) == ("New title", "high", "Ali Khan")


def test_patch_only_changes_sent_fields(client):
    task = make(client, priority="high", due_date=iso(5))
    data = client.patch(f"/api/v1/tasks/{task['id']}", json={"description": "x"}).json()["data"]
    assert data["priority"] == "high" and data["due_date"] == task["due_date"]


def test_patch_null_clears_a_date(client):
    task = make(client, due_date=iso(5))
    data = client.patch(f"/api/v1/tasks/{task['id']}", json={"due_date": None}).json()["data"]
    assert data["due_date"] is None


def test_patch_cannot_blank_title_or_status(client):
    task = make(client)
    assert client.patch(f"/api/v1/tasks/{task['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/api/v1/tasks/{task['id']}", json={"status": None}).status_code == 422


def test_completing_sets_completed_at_and_reopening_clears_it(client):
    task = make(client)
    done = client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "done"}).json()["data"]
    assert done["completed_at"] == NOW.isoformat().replace("+00:00", "Z")
    reopened = client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "in_progress"}).json()["data"]
    assert reopened["completed_at"] is None


def test_create_as_done_has_completed_at(client):
    assert make(client, status="done")["completed_at"] is not None


def test_edit_cannot_put_reminder_after_due_date(client):
    task = make(client, due_date=iso(5), remind_at=iso(1))
    res = client.patch(f"/api/v1/tasks/{task['id']}", json={"remind_at": iso(9)})
    assert res.status_code == 422


# --- delete ---------------------------------------------------------------------
def test_delete_hides_the_task(client):
    task = make(client)
    assert client.delete(f"/api/v1/tasks/{task['id']}").json()["success"] is True
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404
    assert client.get("/api/v1/tasks").json()["meta"]["total"] == 0
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 404


# --- list: filters, sort, paging ---------------------------------------------
@pytest.fixture()
def filled(client):
    make(client, title="Quotation for John", priority="urgent", assignee_id=str(SARA), due_date=iso(-5))
    make(client, title="Invoice review", priority="low", assignee_id=str(ALI), due_date=iso(30),
         description="check tax")
    make(client, title="Team lunch", priority="high", status="in_progress")
    make(client, title="Old task", priority="medium", status="done", due_date=iso(-100))
    return client


def titles(res):
    return [t["title"] for t in res.json()["data"]]


def test_filters(filled):
    c = filled
    assert titles(c.get("/api/v1/tasks?status=in_progress")) == ["Team lunch"]
    assert titles(c.get("/api/v1/tasks?priority=low")) == ["Invoice review"]
    assert titles(c.get(f"/api/v1/tasks?assignee_id={SARA}")) == ["Quotation for John"]
    assert sorted(titles(c.get("/api/v1/tasks?search=TAX"))) == ["Invoice review"]  # searches description, any case
    assert titles(c.get("/api/v1/tasks?overdue=true")) == ["Quotation for John"]  # the done task is not "overdue"


def test_due_before_and_after(filled):
    c = filled
    before = c.get("/api/v1/tasks", params={"due_before": iso(0), "sort": "due_date"})
    assert titles(before) == ["Old task", "Quotation for John"]
    assert titles(c.get("/api/v1/tasks", params={"due_after": iso(0)})) == ["Invoice review"]


def test_sort_by_priority_and_due_date_puts_missing_dates_last(filled):
    c = filled
    assert titles(c.get("/api/v1/tasks?sort=priority")) == ["Quotation for John", "Team lunch", "Old task", "Invoice review"]
    assert titles(c.get("/api/v1/tasks?sort=due_date")) == ["Old task", "Quotation for John", "Invoice review", "Team lunch"]
    assert titles(c.get("/api/v1/tasks?sort=-due_date")) == ["Invoice review", "Quotation for John", "Old task", "Team lunch"]


def test_bad_sort_is_rejected(filled):
    res = filled.get("/api/v1/tasks?sort=colour")
    assert res.status_code == 422 and res.json()["errors"][0]["field"] == "sort"


def test_pagination_meta(filled):
    res = filled.get("/api/v1/tasks?limit=3&page=2&sort=title").json()
    assert res["meta"] == {"page": 2, "limit": 3, "total": 4, "total_pages": 2}
    assert [t["title"] for t in res["data"]] == ["Team lunch"]
    assert filled.get("/api/v1/tasks?limit=101").status_code == 422
    assert filled.get("/api/v1/tasks?page=0").status_code == 422


def test_assignees_endpoint(client):
    names = [a["full_name"] for a in client.get("/api/v1/assignees").json()["data"]]
    assert "Aamna Hameed" in names and len(names) == 4


def test_unknown_route_uses_standard_error_shape(client):
    res = client.get("/api/v1/nope")
    assert res.status_code == 404 and res.json()["success"] is False


def test_sample_data_seeds_every_state():
    app = create_app(now_fn=lambda: NOW, seed=True)
    c = TestClient(app)
    data = c.get("/api/v1/tasks?limit=100").json()["data"]
    assert {t["status"] for t in data} == {"todo", "in_progress", "done", "cancelled"}
    assert any(t["is_overdue"] for t in data)
