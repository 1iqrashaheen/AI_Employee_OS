"""Reminder and progress rules, checked against a fixed clock."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import SAMPLE_ASSIGNEES, TaskStore

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
ALI = SAMPLE_ASSIGNEES[0].id


def iso(hours=0):
    return (NOW + timedelta(hours=hours)).isoformat()


@pytest.fixture()
def client():
    return TestClient(create_app(store=TaskStore(), now_fn=lambda: NOW, seed=False))


def make(client, title, **fields):
    res = client.post("/api/v1/tasks", json={"title": title, **fields})
    assert res.status_code == 201, res.text
    return res.json()["data"]


def reminders(client, query=""):
    res = client.get("/api/v1/tasks/reminders" + query)
    assert res.status_code == 200
    return [(r["reminder_type"], r["task"]["title"]) for r in res.json()["data"]]


# --- reminders ------------------------------------------------------------------
def test_overdue_due_soon_and_reminder_are_classified(client):
    make(client, "late", due_date=iso(-2))
    make(client, "soon", due_date=iso(5))
    make(client, "later", due_date=iso(72))  # not due for 3 days: no reminder
    make(client, "nudge", due_date=iso(72), remind_at=iso(-1))  # own reminder time has passed
    make(client, "no dates")
    assert reminders(client) == [
        ("overdue", "late"), ("due_soon", "soon"), ("reminder", "nudge"),
    ]


def test_finished_tasks_never_appear(client):
    make(client, "done late", due_date=iso(-2), status="done")
    make(client, "cancelled late", due_date=iso(-2), status="cancelled")
    assert reminders(client) == []


def test_task_is_listed_once_overdue_wins_over_reminder(client):
    make(client, "both", due_date=iso(-1), remind_at=iso(-5))
    assert reminders(client) == [("overdue", "both")]


def test_due_soon_window_is_adjustable_and_inclusive(client):
    make(client, "in 24h", due_date=iso(24))
    make(client, "in 48h", due_date=iso(48))
    assert reminders(client) == [("due_soon", "in 24h")]
    assert reminders(client, "?within_hours=48") == [("due_soon", "in 24h"), ("due_soon", "in 48h")]
    assert client.get("/api/v1/tasks/reminders?within_hours=0").status_code == 422


def test_due_exactly_now_is_due_soon_not_overdue(client):
    make(client, "right now", due_date=iso(0))
    assert reminders(client) == [("due_soon", "right now")]


def test_order_is_most_urgent_first(client):
    make(client, "late 1h", due_date=iso(-1))
    make(client, "late 30h", due_date=iso(-30))
    make(client, "soon 10h", due_date=iso(10))
    make(client, "soon 2h", due_date=iso(2))
    assert [t for _, t in reminders(client)] == ["late 30h", "late 1h", "soon 2h", "soon 10h"]


def test_reminder_messages_are_readable(client):
    make(client, "a", due_date=iso(-3))
    make(client, "b", due_date=iso(-72))
    make(client, "c", due_date=iso(5))
    make(client, "d", due_date=iso(0.5))
    msgs = {r["task"]["title"]: r["message"] for r in client.get("/api/v1/tasks/reminders").json()["data"]}
    assert msgs == {"a": "Overdue by 3 hours", "b": "Overdue by 3 days",
                    "c": "Due in 5 hours", "d": "Due within the hour"}


def test_completing_a_task_removes_its_reminder(client):
    task = make(client, "late", due_date=iso(-2))
    assert reminders(client) == [("overdue", "late")]
    client.patch(f"/api/v1/tasks/{task['id']}", json={"status": "done"})
    assert reminders(client) == []


def test_extending_the_due_date_removes_overdue(client):
    task = make(client, "late", due_date=iso(-2))
    client.patch(f"/api/v1/tasks/{task['id']}", json={"due_date": iso(100)})
    assert reminders(client) == []


def test_is_overdue_flag_on_task(client):
    late = make(client, "late", due_date=iso(-2))
    done = make(client, "done", due_date=iso(-2), status="done")
    assert late["is_overdue"] is True and done["is_overdue"] is False


# --- progress -------------------------------------------------------------------
def progress(client, query=""):
    res = client.get("/api/v1/tasks/progress" + query)
    assert res.status_code == 200
    return res.json()["data"]


def test_progress_on_empty_store_is_zero_not_an_error(client):
    p = progress(client)
    assert p["total"] == 0 and p["completed_percent"] == 0.0


def test_progress_counts_and_percent(client):
    make(client, "t1")
    make(client, "t2", status="in_progress", priority="urgent", due_date=iso(-1))
    make(client, "t3", status="done")
    make(client, "t4", status="done")
    make(client, "t5", status="cancelled")
    make(client, "t6", due_date=iso(3), priority="high")
    p = progress(client)
    assert p["total"] == 6
    assert p["by_status"] == {"todo": 2, "in_progress": 1, "done": 2, "cancelled": 1}
    assert p["open_by_priority"] == {"urgent": 1, "high": 1, "medium": 1, "low": 0}
    assert p["completed_percent"] == 40.0  # 2 done of 5 (cancelled is not counted)
    assert (p["overdue"], p["due_soon"]) == (1, 1)


def test_progress_per_person(client):
    make(client, "mine", assignee_id=str(ALI), status="done")
    make(client, "mine too", assignee_id=str(ALI))
    make(client, "someone else")
    p = progress(client, f"?assignee_id={ALI}")
    assert p["total"] == 2 and p["completed_percent"] == 50.0


def test_deleted_tasks_do_not_count(client):
    task = make(client, "gone")
    client.delete(f"/api/v1/tasks/{task['id']}")
    assert progress(client)["total"] == 0
