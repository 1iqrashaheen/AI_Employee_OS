"""Run summarize + classify over all sample emails and write docs/day4_analysis_results.md.

Compares the AI's priority and category with the hand-labelled `expected` answers.
Usage (from backend/):  python scripts/run_analysis_examples.py
Needs LLM_PROVIDER and LLM_API_KEY in ../.env. With LLM_PROVIDER=mock it runs offline (canned answers).
"""
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, llm  # noqa: E402
from app.analysis import classify_email, summarize_email  # noqa: E402
from app.schemas import AnalyzeRequest  # noqa: E402
from app.store import load_emails  # noqa: E402

if not llm.is_configured():
    sys.exit("Set LLM_PROVIDER and LLM_API_KEY in .env first (or LLM_PROVIDER=mock for an offline dry run).")

emails = load_emails()
rows, prio_ok, cat_ok, errors = [], 0, 0, 0
confusion = Counter()


def cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", "<br>")


for e in emails:
    req = AnalyzeRequest(subject=e.subject, body=e.body, sender=e.sender)
    try:
        s = summarize_email(req)
        c = classify_email(req)
    except llm.LLMError as err:
        errors += 1
        rows.append([e.id, e.subject, f"{e.expected.priority.value} / {e.expected.category}", "ERROR", "-", str(err), "-"])
        continue
    p_ok = c.priority == e.expected.priority
    c_ok = c.category == e.expected.category
    prio_ok += p_ok
    cat_ok += c_ok
    confusion[(e.expected.priority.value, c.priority.value)] += 1
    verdict = ("priority OK" if p_ok else f"PRIORITY: expected {e.expected.priority.value}") + (
        ", category OK" if c_ok else f", category: expected {e.expected.category}"
    )
    flag = " ⚠ suspicious" if c.suspicious else ""
    actions = "; ".join(s.action_items) or "-"
    rows.append([
        e.id, e.subject, f"{e.expected.priority.value} / {e.expected.category}",
        f"{c.priority.value} / {c.category}{flag}", verdict, s.summary, actions,
    ])

n = len(emails)
done = n - errors
out = [
    "# Day 4: Summarize and classify results",
    "",
    f"Provider: `{config.LLM_PROVIDER}` · Model: `{llm._model() or 'n/a'}` · Run date: {date.today()} · Emails: {n}",
    "",
]
if config.LLM_PROVIDER == "mock":
    out += ["> **Mock run.** Answers are canned, so the accuracy numbers below say nothing about quality. Re-run with a real provider.", ""]
out += [
    f"**Priority matches my label:** {prio_ok}/{done} · **Category matches:** {cat_ok}/{done} · **Errors:** {errors}",
    "",
    "A mismatch is not always an AI mistake: some labels are judgment calls. Read each mismatch and decide whether to fix the prompt or the label.",
    "",
    "| Expected → Got | Count |", "|---|---|",
]
for (exp, got), cnt in sorted(confusion.items()):
    out.append(f"| {exp} → {got} | {cnt} |")
out += ["", "| ID | Subject | Expected | Got | Check | Summary | Action items |", "|---|---|---|---|---|---|---|"]
out += ["| " + " | ".join(cell(x) for x in r) + " |" for r in rows]

path = ROOT / "docs" / "day4_analysis_results.md"
path.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Wrote {path}  (priority {prio_ok}/{done}, category {cat_ok}/{done}, errors {errors})")
