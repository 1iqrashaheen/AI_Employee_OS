"""Safety net for every test: never touch the developer's real drafts, token, activity log or the real internet."""
import httpx
import pytest

from app import config, http, main
from app.activity import ActivityLog


def _no_internet(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"A test tried to call the real internet: {request.url}")


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_TOKEN_FILE", tmp_path / "isolated.google.token.json")
    monkeypatch.setattr(config, "ACTIVITY_FILE", tmp_path / "isolated.activity.jsonl")
    monkeypatch.setattr(main, "activity", ActivityLog(tmp_path / "isolated.activity.jsonl"))
    monkeypatch.setattr(http, "TRANSPORT", httpx.MockTransport(_no_internet))
