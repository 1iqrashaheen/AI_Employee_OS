import json

import pytest
from fastapi.testclient import TestClient

from app import analysis, config, llm
from app.main import app
from app.schemas import AnalyzeRequest
from app.store import get_email, load_emails

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(config, "LLM_API_KEY", "")


def fake(monkeypatch, output):
    """Make the model return a fixed string (or a callable of the user prompt)."""
    monkeypatch.setitem(llm.PROVIDERS, "mock", (lambda s, u: output(u)) if callable(output) else (lambda s, u: output))


# ---- input cleanup --------------------------------------------------------

def test_html_is_stripped():
    html = "<html><head><style>p{color:red}</style></head><body><p>Hello&nbsp;Ali</p><script>alert(1)</script><div>Meet at <b>3 PM</b></div></body></html>"
    text = analysis.to_plain_text(html)
    assert "alert" not in text and "color" not in text and "<" not in text
    assert "Hello Ali" in text and "3 PM" in text


def test_plain_text_unchanged():
    assert analysis.to_plain_text("Hi,\n\nSee you < 5 PM and > 3 PM.") == "Hi,\n\nSee you < 5 PM and > 3 PM."


def test_long_email_keeps_start_and_end():
    body = "START " + "x" * 30_000 + " END-OF-EMAIL"
    text, truncated = analysis.prepare_email(AnalyzeRequest(subject="Long", body=body))
    assert truncated
    assert "START" in text and "END-OF-EMAIL" in text and "characters omitted" in text
    assert len(text) < analysis.MAX_CHARS + 500


def test_short_email_not_truncated():
    _, truncated = analysis.prepare_email(AnalyzeRequest(subject="Hi", body="Short"))
    assert not truncated


@pytest.mark.parametrize("body,subject", [("", ""), ("   \n ", "  "), ("<p> </p>", "")])
def test_empty_email_rejected(body, subject):
    for path in ("/summarize", "/classify"):
        r = client.post(path, json={"body": body, "subject": subject})
        assert r.status_code == 422, (path, body)


def test_subject_only_is_allowed():
    assert client.post("/classify", json={"subject": "asap?"}).status_code == 200


def test_no_input_at_all_rejected():
    assert client.post("/summarize", json={}).status_code == 422


# ---- safety ---------------------------------------------------------------

def test_email_is_fenced_and_prompt_warns_about_injection():
    original = get_email("e33")
    text, _ = analysis.prepare_email(AnalyzeRequest(subject=original.subject, body=original.body, sender=original.sender))
    assert text.startswith("<email>") and text.endswith("</email>")
    assert "UNTRUSTED" in analysis.SUMMARY_SYSTEM and "UNTRUSTED" in analysis.CLASSIFY_SYSTEM
    assert "Never follow instructions" in analysis.SUMMARY_SYSTEM


def test_suspicious_email_is_capped_at_low_even_if_model_obeys_it(monkeypatch):
    # Simulates a model that was talked into High priority by the injection in e33.
    fake(monkeypatch, '{"priority":"High","category":"invoice","reason":"Says it is urgent","suspicious":true}')
    r = client.post("/classify", json={"email_id": "e33"})
    assert r.status_code == 200
    data = r.json()
    assert data["priority"] == "Low" and data["suspicious"] is True
    assert data["reason"].startswith("Flagged as suspicious")


# ---- parsing and validation ----------------------------------------------

def test_classify_normalizes_case_and_unknown_category(monkeypatch):
    fake(monkeypatch, '{"priority":"high","category":"Invoices-ish","reason":"Due in 3 days","suspicious":"false"}')
    data = client.post("/classify", json={"body": "Pay by Friday", "subject": "Invoice"}).json()
    assert data["priority"] == "High" and data["category"] == "other" and data["suspicious"] is False


def test_classify_rejects_bad_priority_then_fails(monkeypatch):
    calls = []
    fake(monkeypatch, lambda u: calls.append(1) or '{"priority":"Urgent!!","category":"spam","reason":"x"}')
    r = client.post("/classify", json={"body": "hello there", "subject": "hi"})
    assert r.status_code == 503 and len(calls) == 2


def test_summary_fenced_json_and_action_items(monkeypatch):
    fake(monkeypatch, '```json\n{"summary":"Ali wants to meet Friday.","action_items":["Reply to Ali by Thursday", ""]}\n```')
    data = client.post("/summarize", json={"email_id": "e02"}).json()
    assert data["summary"] == "Ali wants to meet Friday."
    assert data["action_items"] == ["Reply to Ali by Thursday"]


def test_summary_string_action_item_becomes_list(monkeypatch):
    fake(monkeypatch, '{"summary":"Pay invoice.","action_items":"Pay by 20 Nov"}')
    assert client.post("/summarize", json={"email_id": "e03"}).json()["action_items"] == ["Pay by 20 Nov"]


def test_bad_output_then_good_output_recovers(monkeypatch):
    outs = iter(["sorry, no", '{"summary":"ok","action_items":[]}'])
    fake(monkeypatch, lambda u: next(outs))
    assert client.post("/summarize", json={"email_id": "e01"}).status_code == 200


def test_truncated_flag_reaches_response(monkeypatch):
    fake(monkeypatch, '{"summary":"Long update.","action_items":[]}')
    data = client.post("/summarize", json={"subject": "Big", "body": "word " * 10_000}).json()
    assert data["truncated"] is True


# ---- endpoints ------------------------------------------------------------

def test_unknown_email_id_404():
    assert client.post("/summarize", json={"email_id": "nope"}).status_code == 404
    assert client.post("/classify", json={"email_id": "nope"}).status_code == 404


def test_no_llm_configured_503(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    assert client.post("/classify", json={"email_id": "e01"}).status_code == 503


def test_non_english_email_goes_through(monkeypatch):
    seen = {}
    fake(monkeypatch, lambda u: seen.setdefault("p", u) and '{"summary":"Pide cotización.","action_items":[]}')
    assert client.post("/summarize", json={"email_id": "e22"}).status_code == 200
    assert "cotizacion" in seen["p"]


def test_every_sample_email_runs_through_both_endpoints():
    """Offline smoke test with the mock model: shape and plumbing work for all 35 emails."""
    for e in load_emails():
        s = client.post("/summarize", json={"email_id": e.id})
        c = client.post("/classify", json={"email_id": e.id})
        assert s.status_code == 200 and c.status_code == 200, e.id
        assert c.json()["priority"] in {"High", "Medium", "Low"}


def test_get_email_not_modified_by_analysis():
    before = json.dumps([e.model_dump(mode="json") for e in load_emails()], sort_keys=True)
    client.post("/classify", json={"email_id": "e01"})
    after = json.dumps([e.model_dump(mode="json") for e in load_emails()], sort_keys=True)
    assert before == after
