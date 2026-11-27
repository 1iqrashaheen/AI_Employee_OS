from collections import Counter

from fastapi.testclient import TestClient

from app.main import app
from app.store import load_emails

client = TestClient(app)


def test_dataset_loads_and_is_valid():
    emails = load_emails()
    assert 30 <= len(emails) <= 40


def test_ids_unique():
    ids = [e.id for e in load_emails()]
    assert len(ids) == len(set(ids))


def test_every_email_has_expected_labels():
    for e in load_emails():
        assert e.expected is not None, e.id
        assert e.body.strip(), e.id


def test_dataset_is_varied():
    emails = load_emails()
    cats = Counter(e.expected.category for e in emails)
    prios = Counter(e.expected.priority.value for e in emails)
    for needed in ["spam", "invoice", "complaint", "meeting", "sales", "unclear"]:
        assert cats[needed] >= 1, needed
    assert set(prios) == {"High", "Medium", "Low"}
    assert max(len(e.body) for e in emails) > 1000  # at least one long email
    assert any("ignore all previous instructions" in e.body.lower() for e in emails)


def test_api_health_and_emails():
    assert client.get("/health").json()["status"] == "ok"
    data = client.get("/emails").json()
    assert len(data) == len(load_emails())
    assert "from" in data[0] and data[0]["status"] == "unread"


def test_api_single_and_404():
    assert client.get("/emails/e01").status_code == 200
    assert client.get("/emails/nope").status_code == 404
