"""Run the Day 9 evaluation (20 cases) and write docs/day9_evaluation_<provider>.md.

Usage (from backend/):
  python scripts/run_evaluation.py              # uses LLM_PROVIDER / LLM_API_KEY from ../.env (your real AI)
  python scripts/run_evaluation.py --reference  # scripted good answers: checks the pipeline and the checks, NOT an AI
  python scripts/run_evaluation.py --mock       # the offline mock model (canned answers; summary/priority checks fail)
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import config, evalkit, llm  # noqa: E402

if "--reference" in sys.argv:
    evalkit.install_reference_model()
    label, note = "reference (scripted)", (
        "> **Scripted run.** The model is replaced by stored good answers, so this run tests the pipeline (prompts, parsing, safety rules) "
        "and the checks themselves. It does **not** measure how good a real AI is. Run `python scripts/run_evaluation.py` with your "
        "own key for that."
    )
elif "--mock" in sys.argv:
    config.LLM_PROVIDER = "mock"
    label, note = "mock", "> **Mock run.** The offline mock gives canned answers. Draft checks can pass because the mock repeats your instruction; the summary and priority checks are expected to fail. Not a quality result."
else:
    if not llm.is_configured():
        sys.exit("Set LLM_PROVIDER and LLM_API_KEY in .env first, or use --reference / --mock.")
    label, note = f"{config.LLM_PROVIDER} · {llm._model() or 'n/a'}", ""

results = evalkit.run_all()
passed = sum(r.passed for r in results)


def cell(text: str, limit: int = 260) -> str:
    text = text.replace("|", "\\|").replace("\n", "<br>")
    return text if len(text) <= limit else text[: limit - 1] + "…"


by_kind = {}
for r in results:
    by_kind.setdefault(r.kind, []).append(r.passed)
lines = [
    "# Day 9: Evaluation results",
    "",
    f"Provider: `{label}` · Run date: {date.today()} · Cases: {len(results)} (data/eval_cases.json)",
    "",
]
if note:
    lines += [note, ""]
lines += [
    f"**Passed {passed}/{len(results)}** · "
    + " · ".join(f"{k}: {sum(v)}/{len(v)}" for k, v in by_kind.items()),
    "",
    "What the checks test: required details present, invented details absent, language, length, priority, category, suspicious flag, and the safety rules. They do not judge writing style; read the outputs for that.",
    "",
    "| ID | Type | Case | Input | Result | What failed | Output |",
    "|---|---|---|---|---|---|---|",
]
for r in results:
    lines.append(
        "| " + " | ".join(cell(x) for x in [r.id, r.kind, r.title, r.input, "PASS" if r.passed else "FAIL", "; ".join(r.failures) or "-", r.output or "-"]) + " |"
    )
out = ROOT / "docs" / f"day9_evaluation_{label.split()[0]}.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Wrote {out}  ({passed}/{len(results)} passed)")
sys.exit(0 if passed == len(results) or "--mock" in sys.argv else 1)
