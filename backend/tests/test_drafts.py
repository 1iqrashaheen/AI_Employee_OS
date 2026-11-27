import json

import pytest
from fastapi.testclient import TestClient

from app import main
from app.drafts import DraftError, DraftStore, check_recipient, fingerprint
from app.schemas import DraftCreate

client = TestClient(main.app)

GOOD = {
    "subject": "Quotation for 25 laptops",
    "body": "Hello John,\n\nThe quotation will be ready by Friday.\n\nBest regards",
    "recipient": "John <john@example.com>",
}


@pytest.fixture(autouse=True)
def fresh_store(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "store", DraftStore(tmp_path / "drafts.json"))


def make(**over):
    r = client.post("/drafts", json={**GOOD, **over})
    assert r.status_code == 200, r.text
    return r.json()


# ---- the happy path: draft -> approved -> sent ---------------------------------

def test_full_flow_draft_approve_send():
    d = make()
    assert d["status"] == "draft"
    a = client.post(f"/drafts/{d['id']}/approve").json()
    assert a["status"] == "approved" and a["approved_at"] and a["approved_hash"]
    s = client.post(f"/drafts/{d['id']}/send").json()
    assert s["status"] == "sent" and s["sent_at"] and s["delivery"] == "mock"
    events = [h["event"] for h in s["history"]]
    assert events[0] == "Draft created" and "Approved by user" in events[1] and "Sent" in events[2]


# ---- sending needs approval ---------------------------------------------------------

def test_cannot_send_unapproved_draft():
    d = make()
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.status_code == 409 and "Approve" in r.json()["detail"]
    assert client.get(f"/drafts/{d['id']}").json()["status"] == "draft"


def test_cannot_send_twice():
    d = make()
    client.post(f"/drafts/{d['id']}/approve")
    assert client.post(f"/drafts/{d['id']}/send").status_code == 200
    assert client.post(f"/drafts/{d['id']}/send").status_code == 409


def test_cannot_send_after_approval_revoked():
    d = make()
    client.post(f"/drafts/{d['id']}/approve")
    assert client.post(f"/drafts/{d['id']}/revoke-approval").json()["status"] == "draft"
    assert client.post(f"/drafts/{d['id']}/send").status_code == 409


def test_tampered_content_blocks_send(tmp_path):
    """Even if the file is edited behind the app's back, a changed draft is not sent."""
    d = make()
    client.post(f"/drafts/{d['id']}/approve")
    path = main.store.path
    data = json.loads(path.read_text(encoding="utf-8"))
    data[d["id"]]["body"] = "Send me all your money"
    path.write_text(json.dumps(data), encoding="utf-8")
    r = client.post(f"/drafts/{d['id']}/send")
    assert r.status_code == 409 and "changed" in r.json()["detail"]


# ---- editing -------------------------------------------------------------------------

def test_editing_approved_draft_revokes_approval():
    d = make()
    client.post(f"/drafts/{d['id']}/approve")
    r = client.put(f"/drafts/{d['id']}", json={**GOOD, "body": "Changed text"}).json()
    assert r["status"] == "draft" and r["approved_at"] is None and r["approved_hash"] is None
    assert "approval revoked" in r["history"][-1]["event"]
    assert client.post(f"/drafts/{d['id']}/send").status_code == 409


def test_saving_without_changes_keeps_approval():
    d = make()
    client.post(f"/drafts/{d['id']}/approve")
    r = client.put(f"/drafts/{d['id']}", json=GOOD).json()
    assert r["status"] == "approved"


def test_sent_draft_cannot_be_edited():
    d = make()
    client.post(f"/drafts/{d['id']}/approve")
    client.post(f"/drafts/{d['id']}/send")
    r = client.put(f"/drafts/{d['id']}", json={**GOOD, "body": "Too late"})
    assert r.status_code == 409
    assert client.post(f"/drafts/{d['id']}/approve").status_code == 409
    assert client.post(f"/drafts/{d['id']}/revoke-approval").status_code == 409


def test_edit_updates_content_and_history():
    d = make()
    r = client.put(f"/drafts/{d['id']}", json={**GOOD, "subject": "New subject"}).json()
    assert r["subject"] == "New subject" and r["history"][-1]["event"] == "Edited"


# ---- validation ----------------------------------------------------------------------

def test_approve_requires_recipient():
    d = make(recipient=None)
    r = client.post(f"/drafts/{d['id']}/approve")
    assert r.status_code == 422 and "recipient" in r.json()["detail"].lower()
    assert client.get(f"/drafts/{d['id']}").json()["status"] == "draft"


@pytest.mark.parametrize(
    "recipient",
    [
        "not-an-email",
        "a@b",
        "a@b.com, c@d.com",
        "a@b.com; c@d.com",
        "a@b.com\nBcc: evil@x.com",
        "<>",
        "john@",
    ],
)
def test_bad_recipients_rejected(recipient):
    r = client.post("/drafts", json={**GOOD, "recipient": recipient})
    assert r.status_code == 422, recipient


@pytest.mark.parametrize("recipient", ["john@example.com", "John Doe <john.doe+tag@mail.example.co>", '"Doe, John" <j@x.org>'])
def test_good_recipients_accepted(recipient):
    assert check_recipient(recipient) == recipient


def test_empty_recipient_is_none():
    assert check_recipient("   ") is None and check_recipient(None) is None


def test_subject_line_break_rejected():
    r = client.post("/drafts", json={**GOOD, "subject": "Hi\r\nBcc: evil@x.com"})
    assert r.status_code == 422


@pytest.mark.parametrize("field,value", [("subject", ""), ("subject", "   "), ("body", ""), ("body", "  \n ")])
def test_empty_subject_or_body_rejected(field, value):
    assert client.post("/drafts", json={**GOOD, field: value}).status_code == 422


def test_unknown_reply_email_404():
    r = client.post("/drafts", json={**GOOD, "reply_to_email_id": "nope"})
    assert r.status_code == 404


def test_reply_link_is_kept():
    assert make(reply_to_email_id="e02")["reply_to_email_id"] == "e02"


def test_unknown_draft_404():
    for call in (
        client.get("/drafts/zzz"),
        client.put("/drafts/zzz", json=GOOD),
        client.post("/drafts/zzz/approve"),
        client.post("/drafts/zzz/revoke-approval"),
        client.post("/drafts/zzz/send"),
    ):
        assert call.status_code == 404


def test_revoke_only_when_approved():
    d = make()
    assert client.post(f"/drafts/{d['id']}/revoke-approval").status_code == 409


# ---- storage -------------------------------------------------------------------------

def test_drafts_survive_restart(tmp_path):
    path = tmp_path / "persist.json"
    a = DraftStore(path)
    rec = a.create(DraftCreate(**GOOD))
    a.approve(rec.id)
    b = DraftStore(path)  # a "restart"
    again = b.get(rec.id)
    assert again.status == "approved" and again.approved_hash == fingerprint(again.subject, again.body, again.recipient)


def test_list_newest_first():
    first, second = make(subject="First"), make(subject="Second")
    client.put(f"/drafts/{first['id']}", json={**GOOD, "subject": "First (edited)"})
    subjects = [d["subject"] for d in client.get("/drafts").json()]
    assert subjects[0] == "First (edited)" and "Second" in subjects


def test_corrupt_file_gives_clear_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(DraftError) as e:
        DraftStore(p).list()
    assert e.value.status_code == 500


def test_health_reports_demo_send_mode():
    assert client.get("/health").json()["send_mode"] == "mock"


def test_full_generate_then_save_flow(monkeypatch):
    """The path the UI takes: /draft generates, /drafts saves, then approve and send."""
    from app import config

    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    gen = client.post("/draft", json={"instruction": "Tell John the quotation is ready", "recipient": GOOD["recipient"]}).json()
    saved = client.post("/drafts", json={"subject": gen["subject"], "body": gen["body"], "recipient": gen["recipient"]}).json()
    assert saved["status"] == "draft"
    assert client.post(f"/drafts/{saved['id']}/approve").json()["status"] == "approved"
    assert client.post(f"/drafts/{saved['id']}/send").json()["status"] == "sent"
