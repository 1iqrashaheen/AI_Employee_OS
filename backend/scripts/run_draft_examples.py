"""Run the 10 draft test instructions through the configured LLM and write docs/day3_draft_examples.md.

Usage (from backend/):  python scripts/run_draft_examples.py
Needs LLM_PROVIDER and LLM_API_KEY in ../.env. With LLM_PROVIDER=mock it runs offline (output is canned).
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, llm  # noqa: E402
from app.drafting import draft_email  # noqa: E402
from app.schemas import DraftRequest  # noqa: E402

cases = json.loads((ROOT / "data" / "draft_test_instructions.json").read_text(encoding="utf-8"))
if not llm.is_configured():
    sys.exit("Set LLM_PROVIDER and LLM_API_KEY in .env first (or LLM_PROVIDER=mock for an offline dry run).")

lines = [
    "# Day 3: Draft test results",
    "",
    f"Provider: `{config.LLM_PROVIDER}` · Model: `{llm._model() or 'n/a'}` · Run date: {date.today()}",
    "",
]
if config.LLM_PROVIDER == "mock":
    lines += ["> **Mock run.** Output is canned, so the Pass/Fail column below is NOT a quality result. Re-run with a real provider.", ""]
lines += ["| # | Instruction | Tone | Expected | Subject | Body | Notes |", "|---|---|---|---|---|---|---|"]


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


for c in cases:
    try:
        d = draft_email(DraftRequest(instruction=c["instruction"], tone=c["tone"], recipient=c["recipient"]))
        row = [c["id"], c["instruction"], c["tone"], c["check"], d.subject, d.body, "; ".join(d.notes) or "-"]
    except llm.LLMError as e:
        row = [c["id"], c["instruction"], c["tone"], c["check"], "ERROR", str(e), "-"]
    lines.append("| " + " | ".join(cell(x) for x in row) + " |")

lines += ["", "After a real run, read each draft and mark it Pass or Fix against the Expected column, then tighten the prompt in `app/drafting.py` for any Fix."]
out = ROOT / "docs" / "day3_draft_examples.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {out}")
