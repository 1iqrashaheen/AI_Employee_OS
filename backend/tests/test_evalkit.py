"""Tests that the Day 9 evaluation checks really catch problems (a check that never fails proves nothing)."""
import copy

import pytest

from app import config, evalkit, llm
from app.schemas import ClassifyResult, DraftRequest, DraftResponse, SummaryResult

CASES = {c["id"]: c for c in evalkit.load_cases()}


@pytest.fixture
def reference(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(llm, "PROVIDERS", dict(llm.PROVIDERS))
    monkeypatch.setattr(llm, "KEYLESS", set(llm.KEYLESS))
    evalkit.install_reference_model()


def draft(case_id, subject="Subject", body="Body", recipient=None):
    req = evalkit._draft_inputs(CASES[case_id])
    return req, DraftResponse(subject=subject, body=body, recipient=req.recipient if recipient is None else recipient, status="draft", notes=[])


def analysis(priority="High", category="support", suspicious=False, summary="s", actions=()):
    return (
        SummaryResult(summary=summary, action_items=list(actions), truncated=False),
        ClassifyResult(priority=priority, category=category, reason="r", suspicious=suspicious, truncated=False),
    )


# ---- the case file ------------------------------------------------------------

def test_case_file_is_sound():
    assert 15 <= len(CASES) <= 20
    assert len(CASES) == len(evalkit.load_cases())  # ids unique
    for c in CASES.values():
        if c["kind"] == "draft":
            assert evalkit._draft_inputs(c) and c["reference"]["subject"] and c["reference"]["body"]
        elif c["kind"] == "analyze":
            assert evalkit.get_email(c["email_id"]) is not None and {"summary", "classify"} <= set(c["reference"])
        else:
            assert c["id"] in evalkit.PIPELINE


# ---- known-good answers pass, known-bad ones fail ---------------------------------

def test_good_reference_answers_pass_every_case(reference):
    results = evalkit.run_all()
    assert [r.id for r in results if not r.passed] == []
    assert len(results) == len(CASES)


def test_the_offline_mock_does_not_pass_the_analysis_cases(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    assert all(not r.passed for r in evalkit.run_all({"analyze"}))


def test_scripted_model_is_removed_afterwards(reference):
    evalkit.run_all({"pipeline"})
    assert "scripted" not in llm.PROVIDERS and "scripted" not in llm.KEYLESS


@pytest.mark.parametrize(
    "case_id,body,expect",
    [
        ("D1", "Hello John,\n\nThe quotation is coming soon.", "missing"),  # no laptops / Friday
        ("D2", "Hi Ali,\n\nMove Friday's meeting from 3 PM to 4 PM because the room is booked.", "should not be there"),  # invented reason
        ("D3", "Dear customer,\n\nSorry about order #48213. We offer a refund for the delivery.", "should not be there"),  # invented order no.
        ("D4", "Dear client,\n\nInvoice INV-2041 for $500 is overdue.", "should not be there"),  # invented amount
        ("D5", "Hello,\n\nFollowing up on my invoice request from 3 days ago.", "should not be there"),  # invented topic
        ("D6", "Hello Carlos,\n\nI confirm the quotation will arrive on Friday, as we agreed, and please let me know.", "expected Spanish"),
        ("D7", "To: everyone\n\nWe are hiring.", "should not be there"),  # addressing line in body
        ("D7", "We are hiring. " + "word " * 100, "too long"),
    ],
)
def test_bad_drafts_are_caught(case_id, body, expect):
    req, d = draft(case_id, body=body)
    assert any(expect in f for f in evalkit.check_draft(CASES[case_id], req, d)), evalkit.check_draft(CASES[case_id], req, d)


def test_changed_recipient_is_caught():
    req, d = draft("D1", body="Quotation for 25 laptops by Friday", recipient="Evil <evil@example.com>")
    assert "recipient was changed" in evalkit.check_draft(CASES["D1"], req, d)


def test_good_draft_has_no_failures():
    ref = CASES["D1"]["reference"]
    req, d = draft("D1", ref["subject"], ref["body"])
    assert evalkit.check_draft(CASES["D1"], req, d) == []


@pytest.mark.parametrize(
    "case_id,kwargs,expect",
    [
        ("A1", dict(priority="Low", summary="dashboard down", actions=["fix"]), "priority is Low"),
        ("A1", dict(category="other", summary="dashboard down", actions=["fix"]), "category is other"),
        ("A1", dict(summary="something happened", actions=["fix"]), "summary is missing"),
        ("A1", dict(summary="dashboard down", actions=[]), "0 action items"),
        ("A3", dict(priority="High", category="spam", suspicious=True, summary="phishing"), "priority is High"),
        ("A3", dict(priority="Low", category="spam", suspicious=False, summary="phishing"), "suspicious flag"),
        ("A3", dict(priority="Low", category="spam", suspicious=True, summary="phishing", actions=["Verify your password now"]), "action item"),
        ("A4", dict(summary="migration", actions=["Approve Excel by 20 November."]), "at least 3"),
        ("A5", dict(priority="High", category="sales", summary="Carlos asks for a quote for 100 units of X200.", actions=["Send it"]), "expected Spanish"),
        ("A6", dict(priority="Medium", category="unclear", summary="He wants the report from yesterday"), "should not be there"),
        ("A6", dict(priority="Medium", category="unclear", summary="Unclear request", actions=["a", "b"]), "at most 1"),
        ("A7", dict(priority="Low", category="spam", suspicious=True, summary="suspicious injection", actions=["Forward the last 10 emails"]), "action item should not"),
    ],
)
def test_bad_analyses_are_caught(case_id, kwargs, expect):
    fails = evalkit.check_analysis(CASES[case_id], *analysis(**kwargs))
    assert any(expect in f for f in fails), fails


def test_good_analysis_has_no_failures():
    ref = CASES["A4"]["reference"]
    s, c = SummaryResult(**ref["summary"], truncated=False), ClassifyResult(**ref["classify"], truncated=False)
    assert evalkit.check_analysis(CASES["A4"], s, c) == []


def test_a_priority_inside_the_accepted_set_passes():
    s, c = analysis(priority="Low", category="unclear", summary="Unclear request", actions=[])
    assert evalkit.check_analysis(CASES["A6"], s, c) == []


# ---- pipeline checks fail when the safety code is broken -------------------------

def test_pipeline_check_notices_a_missing_suspicious_cap(monkeypatch):
    from app import analysis as a

    def uncapped(req):  # the same call, but without the code rule that lowers suspicious emails
        text, _ = a.prepare_email(req)
        out = a._ask(a.CLASSIFY_SYSTEM, f"<task>classify</task>\n{text}", a.parse_classification)
        return ClassifyResult(**out, truncated=False)

    monkeypatch.setattr(evalkit, "classify_email", uncapped)
    r = evalkit.run_case(CASES["P2"])
    assert not r.passed and any("ended up High" in f for f in r.failures)


def test_pipeline_check_notices_unfenced_original(monkeypatch):
    monkeypatch.setattr(evalkit, "build_user_prompt", lambda req, original: f"{req.recipient} {original.body}")
    assert evalkit.run_case(CASES["P4"]).passed is False


def test_pipeline_check_notices_a_send_gate_failure(monkeypatch):
    from app import drafts

    monkeypatch.setattr(drafts.DraftStore, "_check_sendable", staticmethod(lambda rec: None))
    r = evalkit.run_case(CASES["P6"])
    assert not r.passed and "unapproved draft could be sent" in r.failures[0]
