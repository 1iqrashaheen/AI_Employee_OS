"""Regression tests for bugs found in review: tone text, expired-Gmail demo send, lost save after send, leaks, foreign origins."""
import pytest
from fastapi.testclient import TestClient

from app import config, drafts, google_auth, main
from app.drafting import build_user_prompt
from app.main import app
from app.schemas import DraftRequest
from test_google import connect, fake, token_file  # noqa: F401
from test_send import GOOD, approved, connect_with_send, client as send_client

client = TestClient(app, follow_redirects=False)


def test_tone_is_sent_as_plain_word():
    p = build_user_prompt(DraftRequest(instruction="Say hi", tone="friendly"), None)
    assert "<tone>friendly</tone>" in p and "Tone." not in p


def test_plain_recipient_address_is_not_sent_to_model():
    p = build_user_prompt(DraftRequest(instruction="Say hi", recipient="bob.private@example.com"), None)
    assert "bob.private@example.com" not in p and "the recipient" in p


def test_expired_gmail_never_falls_back_to_demo_send(fake):
    connect()
    d = approved()
    google_auth.mark_reauth_required()
    assert client.get("/health").json()["send_mode"] == "reconnect"
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.status_code == 401 and r.json()["code"] == "reauth"
    assert client.get(f"/drafts/{d['id']}").json()["status"] == "approved"


def test_failed_save_after_real_send_blocks_a_second_send(fake, monkeypatch):
    connect_with_send(fake)
    d = approved()
    def boom(*a, **k):
        raise OSError("disk full")
    with monkeypatch.context() as m:
        m.setattr(main.store, "_write", boom)
        assert client.post(f"/drafts/{d['id']}/send").status_code == 500
    assert len(fake.sent) == 1
    assert client.post(f"/drafts/{d['id']}/send").status_code == 409
    assert len(fake.sent) == 1


def test_expected_labels_are_not_exposed():
    assert all("expected" not in e for e in client.get("/emails").json())
    assert "expected" not in client.get("/emails/e1").json()


def test_foreign_origin_cannot_post():
    r = client.post("/auth/google/disconnect", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    ok = client.post("/auth/google/disconnect", headers={"Origin": config.FRONTEND_ORIGIN})
    assert ok.status_code == 200
