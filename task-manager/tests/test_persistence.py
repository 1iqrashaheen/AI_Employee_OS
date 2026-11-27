"""Tasks saved to a file must survive a restart (a new store reading the same file)."""
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store import JsonFileTaskStore

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


def start(path, seed=False):
    """Start the app as if the server had just been launched."""
    store = JsonFileTaskStore(path)
    return TestClient(create_app(store=store, now_fn=lambda: NOW, seed=seed))


def test_tasks_survive_restart(tmp_path):
    file = tmp_path / "tasks.json"
    first = start(file)
    created = first.post("/api/v1/tasks", json={
        "title": "Call John", "priority": "high",
        "due_date": (NOW + timedelta(hours=5)).isoformat(),
    }).json()["data"]

    second = start(file)  # "restart"
    again = second.get(f"/api/v1/tasks/{created['id']}").json()["data"]
    assert again["title"] == "Call John" and again["priority"] == "high"
    assert again["due_date"] == created["due_date"]


def test_edit_and_complete_are_saved(tmp_path):
    file = tmp_path / "tasks.json"
    first = start(file)
    task_id = first.post("/api/v1/tasks", json={"title": "Write report"}).json()["data"]["id"]
    first.patch(f"/api/v1/tasks/{task_id}", json={"title": "Write final report", "status": "done"})

    data = start(file).get(f"/api/v1/tasks/{task_id}").json()["data"]
    assert data["title"] == "Write final report"
    assert data["status"] == "done" and data["completed_at"] is not None


def test_deleted_task_stays_deleted_after_restart(tmp_path):
    file = tmp_path / "tasks.json"
    first = start(file)
    task_id = first.post("/api/v1/tasks", json={"title": "Old"}).json()["data"]["id"]
    first.delete(f"/api/v1/tasks/{task_id}")

    second = start(file)
    assert second.get(f"/api/v1/tasks/{task_id}").status_code == 404
    assert second.get("/api/v1/tasks").json()["meta"]["total"] == 0
    # soft delete: the row is still in the file, marked with deleted_at
    rows = json.loads(file.read_text())
    assert rows[0]["deleted_at"] is not None


def test_samples_are_added_once_not_on_every_restart(tmp_path):
    file = tmp_path / "tasks.json"
    first = start(file, seed=True)
    total = first.get("/api/v1/tasks?limit=100").json()["meta"]["total"]
    assert total == 10

    second = start(file, seed=True)  # file already has tasks, so no new samples
    assert second.get("/api/v1/tasks?limit=100").json()["meta"]["total"] == 10


def test_missing_file_starts_empty_and_is_created_on_first_save(tmp_path):
    file = tmp_path / "new-folder" / "tasks.json"
    client = start(file)
    assert client.get("/api/v1/tasks").json()["meta"]["total"] == 0
    assert not file.exists()
    client.post("/api/v1/tasks", json={"title": "First"})
    assert file.exists()


def test_corrupt_file_gives_a_clear_error_instead_of_silently_starting_empty(tmp_path):
    file = tmp_path / "tasks.json"
    file.write_text("{ this is not json")
    with pytest.raises(RuntimeError, match="Could not read task file"):
        JsonFileTaskStore(file)
