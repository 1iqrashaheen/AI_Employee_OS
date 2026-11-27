"""Evaluation kit (Day 9): automatic checks for drafts, summaries and priorities, plus pipeline safety checks.

Used by scripts/run_evaluation.py (the report) and tests/test_evalkit.py (tests that the checks themselves work).
Cases live in data/eval_cases.json. A check never "grades the writing"; it tests facts that can be tested:
required details present, invented details absent, language, length, priority, flags.
"""
import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import config, llm
from .analysis import EmptyEmailError, classify_email, prepare_email, summarize_email
from .drafting import build_user_prompt, draft_email
from .drafts import DraftError, DraftStore
from .schemas import AnalyzeRequest, ClassifyResult, DraftCreate, DraftRequest, DraftResponse, Email, SummaryResult
from .store import get_email

ROOT = Path(__file__).resolve().parents[2]
CASES_FILE = ROOT / "data" / "eval_cases.json"
DRAFT_CASES_FILE = ROOT / "data" / "draft_test_instructions.json"

ES_WORDS = {"hola", "estimado", "gracias", "saludos", "cordiales", "te", "la", "el", "que", "para", "por", "favor", "una", "los", "con", "del", "cotización", "cotizacion", "viernes", "llegará", "llegara", "solicita", "enviar", "antes", "unidades", "modelo", "confirmo", "carlos"}
EN_WORDS = {"the", "and", "will", "please", "is", "be", "your", "for", "you", "with", "this", "that", "would", "could", "has", "have", "are", "was", "from", "by"}


@dataclass
class CaseResult:
    id: str
    kind: str
    title: str
    input: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    output: str = ""


def load_cases() -> list[dict]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-záéíóúñü]+", text.lower())


def _language_failure(text: str, want: str) -> Optional[str]:
    w = _words(text)
    es = sum(x in ES_WORDS for x in w)
    en = sum(x in EN_WORDS for x in w)
    if want == "es" and not (es >= 3 and en <= 1):
        return f"expected Spanish (Spanish words {es}, English words {en})"
    if want == "en" and es > en:
        return f"expected English (Spanish words {es}, English words {en})"
    return None


def _include_failures(text: str, groups: list[list[str]], what: str) -> list[str]:
    low = text.lower()
    return [f"{what} is missing one of: {' / '.join(g)}" for g in groups if not any(alt.lower() in low for alt in g)]


def _exclude_failures(text: str, patterns: list[str], what: str) -> list[str]:
    out = []
    for p in patterns:
        m = re.search(p, text, re.I | re.M)
        if m:
            out.append(f"{what} contains something that should not be there: '{m.group(0)}'")
    return out


def check_draft(case: dict, request: DraftRequest, draft: DraftResponse) -> list[str]:
    c = case["checks"]
    text = f"{draft.subject}\n{draft.body}"
    fails = _include_failures(text, c.get("include", []), "draft")
    fails += _exclude_failures(text, c.get("exclude_regex", []), "draft")
    # Always: nothing in the body may address anyone, and the recipient must be exactly what the user typed.
    fails += _exclude_failures(draft.body, [r"^\s*(to|cc|bcc)\s*:"], "draft body")
    if draft.recipient != request.recipient:
        fails.append("recipient was changed")
    if len(_words(draft.body)) > c.get("max_words", 150):
        fails.append(f"too long ({len(_words(draft.body))} words, limit {c.get('max_words', 150)})")
    if "language" in c and (f := _language_failure(draft.body, c["language"])):
        fails.append(f)
    return fails


def check_analysis(case: dict, summary: SummaryResult, cls: ClassifyResult) -> list[str]:
    c = case["checks"]
    fails: list[str] = []
    ok_prio = c.get("accept", [c["priority"]]) if "priority" in c else None
    if ok_prio and cls.priority.value not in ok_prio:
        fails.append(f"priority is {cls.priority.value}, expected {' or '.join(ok_prio)}")
    if "category" in c and cls.category != c["category"]:
        fails.append(f"category is {cls.category}, expected {c['category']}")
    if "suspicious" in c and cls.suspicious != c["suspicious"]:
        fails.append(f"suspicious flag is {cls.suspicious}, expected {c['suspicious']}")
    fails += _include_failures(summary.summary, c.get("summary_include", []), "summary")
    fails += _exclude_failures(summary.summary, c.get("summary_exclude_regex", []), "summary")
    actions = summary.action_items
    fails += _include_failures(" ".join(actions), c.get("action_include", []), "action items")
    for p in c.get("action_exclude_regex", []):
        for item in actions:
            if re.search(p, item, re.I):
                fails.append(f"an action item should not say: '{item}'")
    if len(actions) < c.get("min_action_items", 0):
        fails.append(f"{len(actions)} action items, expected at least {c['min_action_items']}")
    if len(actions) > c.get("max_action_items", 99):
        fails.append(f"{len(actions)} action items, expected at most {c['max_action_items']}")
    if "language" in c and (f := _language_failure(summary.summary, c["language"])):
        fails.append(f)
    return fails


# ---- running -----------------------------------------------------------------

def _draft_inputs(case: dict) -> DraftRequest:
    src = {d["id"]: d for d in json.loads(DRAFT_CASES_FILE.read_text(encoding="utf-8"))}[case["source"]]
    return DraftRequest(instruction=src["instruction"], tone=src["tone"], recipient=src["recipient"])


def run_draft_case(case: dict) -> CaseResult:
    req = _draft_inputs(case)
    try:
        d = draft_email(req)
    except llm.LLMError as e:
        return CaseResult(case["id"], "draft", case["title"], req.instruction, False, [f"AI error: {e}"])
    fails = check_draft(case, req, d)
    return CaseResult(case["id"], "draft", case["title"], req.instruction, not fails, fails, f"{d.subject}\n{d.body}")


def run_analyze_case(case: dict) -> CaseResult:
    email = get_email(case["email_id"])
    assert email is not None, case["email_id"]
    req = AnalyzeRequest(subject=email.subject, body=email.body, sender=email.sender)
    label = f"{email.id}: {email.subject}"
    try:
        s, c = summarize_email(req), classify_email(req)
    except llm.LLMError as e:
        return CaseResult(case["id"], "analyze", case["title"], label, False, [f"AI error: {e}"])
    fails = check_analysis(case, s, c)
    out = f"{c.priority.value} / {c.category}{' / suspicious' if c.suspicious else ''}: {s.summary} | actions: {'; '.join(s.action_items) or '-'}"
    return CaseResult(case["id"], "analyze", case["title"], label, not fails, fails, out)


# Pipeline checks drive the real code with a scripted model, so they do not depend on any AI quality.
class _Scripted:
    """Temporarily replaces the model with a function. Records every prompt it receives."""

    def __init__(self, fn: Callable[[str, str], str]):
        self.fn, self.prompts = fn, []

    def __enter__(self):
        self._old = (config.LLM_PROVIDER, llm.PROVIDERS.get("scripted"))
        llm.PROVIDERS["scripted"] = lambda system, user: (self.prompts.append(user), self.fn(system, user))[1]
        config.LLM_PROVIDER = "scripted"
        llm.KEYLESS.add("scripted")
        return self

    def __exit__(self, *exc):
        llm.KEYLESS.discard("scripted")
        config.LLM_PROVIDER = self._old[0]
        if self._old[1] is None:
            llm.PROVIDERS.pop("scripted", None)
        else:
            llm.PROVIDERS["scripted"] = self._old[1]


def _p1() -> list[str]:
    replies = iter(["Sorry, here you go!", json.dumps({"subject": "Hi", "body": "Hello,\n\nHi.\n\nBest regards"})])
    with _Scripted(lambda s, u: next(replies)) as m:
        d = draft_email(DraftRequest(instruction="Say hi", recipient="A <a@example.com>"))
    return ([] if len(m.prompts) == 2 and d.subject == "Hi" else ["did not retry exactly once"])


def _p2() -> list[str]:
    e = get_email("e33")
    bad = json.dumps({"priority": "High", "category": "sales", "reason": "Owner asked to mark High", "suspicious": True})
    with _Scripted(lambda s, u: bad):
        c = classify_email(AnalyzeRequest(subject=e.subject, body=e.body, sender=e.sender))
    fails = []
    if c.priority.value != "Low":
        fails.append(f"suspicious email ended up {c.priority.value}")
    if not c.reason.startswith("Flagged as suspicious"):
        fails.append("reason does not say it was flagged")
    return fails


def _p3() -> list[str]:
    with _Scripted(lambda s, u: "{}") as m:
        try:
            summarize_email(AnalyzeRequest(subject="  ", body="\n \n"))
        except EmptyEmailError:
            return [] if not m.prompts else ["the model was called for an empty email"]
    return ["an empty email was accepted"]


def _p4() -> list[str]:
    e = get_email("e33")
    original = Email(id="x", thread_id="t", **{"from": e.sender}, subject=e.subject, body=e.body, date=e.date)
    req = DraftRequest(instruction="Reply politely", recipient="Zed <zed.private@example.com>")
    prompt = build_user_prompt(req, original)
    fails = []
    if "<original_email>" not in prompt or "</original_email>" not in prompt:
        fails.append("original email is not fenced")
    if "zed.private@example.com" in prompt:
        fails.append("recipient address was sent to the model")
    return fails


def _p5() -> list[str]:
    body = "Start of a long email. " + ("filler sentence. " * 3000) + " The very end."
    text, truncated = prepare_email(AnalyzeRequest(subject="Long", body=body))
    fails = []
    if not truncated:
        fails.append("not marked truncated")
    if "characters omitted" not in text:
        fails.append("the model is not told text was omitted")
    if "Start of a long email" not in text or "The very end." not in text:
        fails.append("start or end of the email was lost")
    return fails


def _p6() -> list[str]:
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        store = DraftStore(Path(tmp) / "d.json")
        rec = store.create(DraftCreate(subject="Hi", body="Hello", recipient="A <a@example.com>"))

        def refused(fn) -> bool:
            try:
                fn()
            except DraftError as e:
                return e.status_code == 409
            return False

        if not refused(lambda: store.send(rec.id)):
            return ["an unapproved draft could be sent"]  # later steps would be meaningless
        store.approve(rec.id)
        store.update(rec.id, DraftCreate(subject="Hi", body="Hello, changed", recipient="A <a@example.com>"))
        if not refused(lambda: store.send(rec.id)):
            return ["a draft edited after approval could be sent"]
        store.approve(rec.id)
        sent = store.send(rec.id)
        if sent.status.value != "sent":
            fails.append("an approved draft was not sent")
        if not refused(lambda: store.send(rec.id)):
            fails.append("the same draft could be sent twice")
    return fails


PIPELINE = {"P1": _p1, "P2": _p2, "P3": _p3, "P4": _p4, "P5": _p5, "P6": _p6}


def run_pipeline_case(case: dict) -> CaseResult:
    try:
        fails = PIPELINE[case["id"]]()
    except Exception as e:  # a crash is a failure, with its reason
        fails = [f"crashed: {type(e).__name__}: {e}"]
    return CaseResult(case["id"], "pipeline", case["title"], "(scripted model)", not fails, fails, "")


def run_case(case: dict) -> CaseResult:
    return {"draft": run_draft_case, "analyze": run_analyze_case, "pipeline": run_pipeline_case}[case["kind"]](case)


def run_all(kinds: Optional[set[str]] = None) -> list[CaseResult]:
    return [run_case(c) for c in load_cases() if not kinds or c["kind"] in kinds]


# ---- scripted "reference" model ----------------------------------------------------

def install_reference_model() -> None:
    """Provider 'reference': answers each evaluation case with its stored good answer.

    This exercises the real prompts, parsing and safety code with known-good replies. It says nothing about how
    good a real AI is; it proves the pipeline and the checks work, so a real model's score can be trusted.
    """
    drafts, analyses = {}, {}
    for c in load_cases():
        if c["kind"] == "draft":
            drafts[_draft_inputs(c).instruction] = c["reference"]
        elif c["kind"] == "analyze":
            analyses[get_email(c["email_id"]).subject] = c["reference"]

    def fn(system: str, user: str) -> str:
        subject = (re.search(r"Subject: (.*)", user) or [None, ""])[1]
        if "<task>summarize</task>" in user:
            return json.dumps(analyses[subject]["summary"])
        if "<task>classify</task>" in user:
            return json.dumps(analyses[subject]["classify"])
        m = re.search(r"<instruction>\n?(.*?)\n?</instruction>", user, re.S)
        return json.dumps(drafts[m.group(1).strip()])

    llm.PROVIDERS["reference"] = lambda system, user: fn(system, user)
    llm.KEYLESS.add("reference")
    config.LLM_PROVIDER = "reference"
