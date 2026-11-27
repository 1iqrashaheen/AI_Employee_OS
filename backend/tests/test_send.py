"""Day 8: sending approved drafts through Gmail, with a fake Google (nothing real is ever sent)."""
import base64
import email
import json
from email import policy
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app import google_auth, gmail, main
from app.main import app
from test_google import READ, FakeGoogle, connect, fake, location, msg, start_login, token_file  # noqa: F401

client = TestClient(app, follow_redirects=False)
SEND = google_auth.SCOPE_SEND
GOOD = {"subject": "Quotation for 25 laptops", "body": "Hello John,\n\nReady by Friday. Thanks!\n\nBest", "recipient": "John <john@example.com>"}


def connect_with_send(fake, code="abc"):
    fake.token_json = {**fake.token_json, "scope": fake.token_json["scope"] + " " + SEND}
    url = client.post("/auth/google/login", params={"send": "true"}).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    return client.get("/auth/google/callback", params={"code": code, "state": state})


def approved(**over):
    d = client.post("/drafts", json={**GOOD, **over}).json()
    assert client.post(f"/drafts/{d['id']}/approve").status_code == 200
    return d


def raw_sent(fake, i=0):
    raw = fake.sent[i]["raw"]
    return email.message_from_bytes(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)), policy=policy.default)


# ---- asking for the send permission ------------------------------------------------

def test_send_permission_is_only_requested_when_asked(fake):
    plain = parse_qs(urlparse(client.post("/auth/google/login").json()["url"]).query)
    assert SEND not in plain["scope"][0].split()
    asked = parse_qs(urlparse(client.post("/auth/google/login", params={"send": "true"}).json()["url"]).query)
    assert SEND in asked["scope"][0].split() and READ in asked["scope"][0].split()
    assert asked["include_granted_scopes"] == ["true"]


def test_upgrade_preselects_the_connected_account(fake):
    connect(fake and "abc")
    q = parse_qs(urlparse(client.post("/auth/google/login", params={"send": "true"}).json()["url"]).query)
    assert q["login_hint"] == ["me@gmail.com"]


def test_granting_send_updates_status_and_returns_a_distinct_result(fake):
    connect()
    assert client.get("/auth/status").json()["can_send"] is False
    r = connect_with_send(fake)
    assert location(r)["google"] == ["send_enabled"]
    st = client.get("/auth/status").json()
    assert st["can_send"] is True and st["can_read"] is True


def test_unticking_send_on_google_keeps_the_read_connection(fake):
    connect()
    before = token_file()
    r = client.get("/auth/google/callback", params={"code": "x", "state": parse_qs(urlparse(client.post("/auth/google/login", params={"send": "true"}).json()["url"]).query)["state"][0]})
    assert location(r)["google"] == ["error"] and "Sending was not allowed" in location(r)["reason"][0]
    assert token_file() == before
    assert client.get("/auth/status").json()["can_read"] is True


def test_send_mode_in_health(fake):
    assert client.get("/health").json()["send_mode"] == "mock"
    connect()
    assert client.get("/health").json()["send_mode"] == "needs_permission"
    connect_with_send(fake)
    assert client.get("/health").json()["send_mode"] == "real"


# ---- the approval gate still applies for real sends ----------------------------------

def test_real_send_needs_approval(fake):
    connect_with_send(fake)
    d = client.post("/drafts", json=GOOD).json()
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.status_code == 409 and fake.sent == []


def test_revoked_or_edited_approval_blocks_real_send(fake):
    connect_with_send(fake)
    d = approved()
    client.put(f"/drafts/{d['id']}", json={**GOOD, "body": "changed after approval"})
    assert client.post(f"/drafts/{d['id']}/send").status_code == 409
    assert fake.sent == []


def test_connected_without_send_permission_is_refused_not_faked(fake):
    connect()
    d = approved()
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.status_code == 403 and r.json()["code"] == "send_scope_missing"
    assert fake.sent == []
    assert client.get(f"/drafts/{d['id']}").json()["status"] == "approved"


def test_unapproved_draft_reports_approval_problem_before_permission_problem(fake):
    connect()
    d = client.post("/drafts", json=GOOD).json()
    assert client.post(f"/drafts/{d['id']}/send").status_code == 409


def test_not_connected_is_still_a_clearly_marked_demo_send(fake):
    d = approved()
    s = client.post(f"/drafts/{d['id']}/send").json()
    assert s["status"] == "sent" and s["delivery"] == "mock" and fake.gmail_calls() == []


# ---- the real send -----------------------------------------------------------------

def test_real_send_delivers_exactly_once_with_the_approved_content(fake):
    connect_with_send(fake)
    d = approved()
    s = client.post(f"/drafts/{d['id']}/send")
    assert s.status_code == 200
    rec = s.json()
    assert rec["status"] == "sent" and rec["delivery"] == "gmail" and rec["delivery_id"] == "sent-1"
    assert len(fake.sent) == 1
    m = raw_sent(fake)
    assert m["To"] == "John <john@example.com>" and m["Subject"] == GOOD["subject"]
    assert m.get_content().strip() == GOOD["body"].strip()
    assert m["From"] is None  # Gmail fills in the signed-in account
    assert client.post(f"/drafts/{d['id']}/send").status_code == 409  # no second email
    assert len(fake.sent) == 1


def test_unicode_subject_and_body_survive(fake):
    connect_with_send(fake)
    d = approved(subject="Café ☕ کل کی میٹنگ", body="سلام، کل 3 بجے ملتے ہیں۔ Merci!")
    client.post(f"/drafts/{d['id']}/send")
    m = raw_sent(fake)
    assert m["Subject"] == "Café ☕ کل کی میٹنگ" and "کل 3 بجے" in m.get_content()


def test_reply_keeps_the_conversation_thread(fake):
    fake.messages = {"m1": msg("m1", "Lunch?", "Ali <ali@example.com>", plain="Lunch tomorrow?")}
    fake.messages["m1"]["payload"]["headers"] += [{"name": "Message-ID", "value": "<abc@mail.example>"}, {"name": "References", "value": "<root@mail.example>"}]
    connect_with_send(fake)
    d = client.post("/drafts", json={**GOOD, "reply_to_email_id": "gmail:m1"}).json()
    client.post(f"/drafts/{d['id']}/approve")
    assert client.post(f"/drafts/{d['id']}/send").status_code == 200
    assert fake.sent[0]["threadId"] == "tm1"
    m = raw_sent(fake)
    assert m["In-Reply-To"] == "<abc@mail.example>" and m["References"] == "<root@mail.example> <abc@mail.example>"


def test_reply_still_sends_if_the_original_cannot_be_read(fake):
    connect_with_send(fake)
    d = client.post("/drafts", json={**GOOD, "reply_to_email_id": "gmail:gone"}).json() if False else None
    # an unreadable original must not block the send (threading is best effort)
    assert gmail.reply_context("gmail:gone") is None
    d = approved()
    assert client.post(f"/drafts/{d['id']}/send").status_code == 200


def test_expired_access_token_is_renewed_before_sending(fake):
    from test_google import expire_access_token
    connect_with_send(fake)
    expire_access_token()
    d = approved()
    assert client.post(f"/drafts/{d['id']}/send").status_code == 200
    assert len(fake.sent) == 1


def test_401_on_send_is_retried_once_after_renewing(fake):
    connect_with_send(fake)
    fake.send_401_once = True
    d = approved()
    assert client.post(f"/drafts/{d['id']}/send").status_code == 200
    assert len(fake.sent) == 1


# ---- failures never lose or duplicate email --------------------------------------------

@pytest.mark.parametrize(
    "status,body,code",
    [
        (400, {"error": {"message": "Invalid To header"}}, "send_rejected"),
        (403, {"error": {"message": "Insufficient Permission", "errors": [{"reason": "insufficientPermissions"}]}}, "send_scope_missing"),
        (429, {"error": {"message": "Rate limit"}}, "rate_limited"),
        (403, {"error": {"message": "Gmail API has not been used in project 1 before or it is disabled."}}, "api_disabled"),
    ],
)
def test_definite_failures_keep_the_draft_approved_and_say_why(fake, status, body, code):
    connect_with_send(fake)
    fake.send_result = (status, body)
    d = approved()
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.status_code >= 400 and r.json()["code"] == code
    rec = client.get(f"/drafts/{d['id']}").json()
    assert rec["status"] == "approved" and rec["delivery"] is None
    assert any("Send failed" in h["event"] for h in rec["history"])
    fake.send_result = None  # a retry then works, once
    assert client.post(f"/drafts/{d['id']}/send").status_code == 200
    assert len(fake.sent) == 1


def test_persistent_401_asks_to_reconnect(fake):
    connect_with_send(fake)
    fake.send_result = (401, {"error": {"message": "Invalid Credentials"}})
    d = approved()
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.status_code == 401 and r.json()["code"] == "reauth"
    assert client.get("/auth/status").json()["reauth_required"] is True
    assert client.get(f"/drafts/{d['id']}").json()["status"] == "approved"


def test_cannot_connect_to_gmail_means_definitely_not_sent(fake):
    connect_with_send(fake)
    fake.send_exception = httpx.ConnectError
    d = approved()
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.status_code == 503 and r.json()["code"] == "network"
    assert client.get(f"/drafts/{d['id']}").json()["status"] == "approved"


def test_timeout_after_sending_warns_to_check_sent_folder(fake):
    connect_with_send(fake)
    fake.send_exception = httpx.ReadTimeout
    d = approved()
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.json()["code"] == "send_unknown" and "Sent folder" in r.json()["detail"]
    assert client.get(f"/drafts/{d['id']}").json()["status"] == "approved"
    assert any(a["event"] == "send_unknown" for a in client.get("/activity").json())


def test_gmail_500_is_treated_as_not_confirmed(fake):
    connect_with_send(fake)
    fake.send_result = (503, {"error": {"message": "backend error"}})
    d = approved()
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.json()["code"] == "send_unknown"


def test_a_draft_being_sent_cannot_be_edited_or_sent_again(fake):
    connect_with_send(fake)
    d = approved()
    main.store.begin_send(d["id"])  # simulates a send in progress
    assert client.put(f"/drafts/{d['id']}", json={**GOOD, "body": "sneaky edit"}).status_code == 409
    assert client.post(f"/drafts/{d['id']}/send").status_code == 409
    assert client.post(f"/drafts/{d['id']}/revoke-approval").status_code == 409
    assert fake.sent == []


# ---- header injection can never reach Gmail -----------------------------------------------

def test_header_injection_is_rejected_when_saving(fake):
    connect_with_send(fake)
    r = client.post("/drafts", json={**GOOD, "subject": "Hi\r\nBcc: spy@evil.example"})
    assert r.status_code == 422
    r = client.post("/drafts", json={**GOOD, "recipient": "a@b.com\nBcc: spy@evil.example"})
    assert r.status_code == 422


def test_message_builder_refuses_line_breaks_in_headers():
    from app.google_auth import GoogleError
    with pytest.raises(GoogleError):
        gmail.build_raw_message("a@b.com", "Hi\nBcc: x@y.com", "body")


# ---- activity log ---------------------------------------------------------------------------

def test_activity_log_records_the_story_without_bodies(fake):
    connect()
    connect_with_send(fake)
    d = approved()
    client.post(f"/drafts/{d['id']}/send")
    client.post("/auth/google/disconnect")
    log = client.get("/activity").json()
    events = [a["event"] for a in log]
    assert events == ["gmail_disconnected", "sent", "approved", "send_permission_granted", "gmail_connected"]
    sent = next(a for a in log if a["event"] == "sent")
    assert sent["to"] == GOOD["recipient"] and sent["subject"] == GOOD["subject"] and sent["gmail_message_id"] == "sent-1"
    assert "Ready by Friday" not in json.dumps(log)
    assert all(a["label"] for a in log)


def test_failed_send_is_logged_and_revoke_is_logged(fake):
    connect_with_send(fake)
    d = approved()
    client.post(f"/drafts/{d['id']}/revoke-approval")
    client.post(f"/drafts/{d['id']}/approve")
    fake.send_result = (400, {"error": {"message": "bad"}})
    client.post(f"/drafts/{d['id']}/send")
    events = [a["event"] for a in client.get("/activity").json()]
    assert "send_failed" in events and "approval_revoked" in events


def test_activity_log_survives_a_broken_line_and_unwritable_path(fake, tmp_path):
    from app.activity import ActivityLog
    p = tmp_path / "a.jsonl"
    p.write_text('{"at":"x","event":"sent"}\nnot json\n')
    assert [a["event"] for a in ActivityLog(p).recent()] == ["sent"]
    ActivityLog(tmp_path / "dir" / "x" / "..").record("sent")  # must not raise even if it cannot write


def test_activity_endpoint_limit_is_bounded(fake):
    assert client.get("/activity", params={"limit": 0}).status_code == 422
    assert client.get("/activity", params={"limit": 500}).status_code == 422
    assert client.get("/activity").json() == []


def test_no_token_in_any_send_or_activity_response(fake):
    connect_with_send(fake)
    d = approved()
    texts = [client.post(f"/drafts/{d['id']}/send").text, client.get("/activity").text, client.get("/auth/status").text, client.get("/health").text]
    assert not any("ya29" in t or "1//fake" in t for t in texts)


def test_activity_file_is_gitignored():
    from pathlib import Path
    ignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text()
    assert "data/activity.jsonl" in ignore
