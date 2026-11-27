# Submission: AI Email Assistant

## Task
- Draft email messages from a short instruction.
- Summarize longer messages and mark important emails.
- Provide an approved send-email option if an authorized email connection is available.
- Before starting: research email service permissions and AI drafting.
- Submit: email draft/summarize feature with tested examples and instructions.
- Connection: can start with sample emails; real sending requires authorized email access.

## What is delivered
| Requirement | Where | Status |
|---|---|---|
| Draft from a short instruction | Compose tab, `POST /draft`, `backend/app/drafting.py` | Done. Tested with 10 instructions (`docs/day3_draft_examples.md`) and 7 in the evaluation |
| Summarize and mark important emails | Inbox tab, `POST /summarize`, `POST /classify`, `backend/app/analysis.py` | Done. 35 labelled sample emails, 7 in the evaluation |
| Approved send option | Approve, then Send with a confirmation window, `backend/app/drafts.py`, `sender.py`, `gmail.py` | Done. Real sending only with an authorized Gmail connection and the separate send permission; otherwise a labelled demo |
| Research: permissions and AI drafting | Day 1 research doc (https://claude.ai/artifact/C6Yp4iTXxZMLCpieMGe3jz) and summary below | Done |
| Tested examples | `data/eval_cases.json` (20 cases), `docs/day9_test_results.md`, 221 backend tests, browser tests | Done (see honest status) |
| Instructions | `README.md`, `docs/day7_google_setup.md`, `docs/day8_sending.md` | Done |
| Start with sample emails | 35 sample emails in `data/sample_emails.json`; app runs with no Google setup | Done |

## Research summary
- **Permissions (Gmail):** least privilege. Reading uses `gmail.readonly`; sending uses `gmail.send`, requested only when the user clicks Allow sending. The app never asks for full mailbox access (`mail.google.com`). OAuth authorization code flow with PKCE and a one-time state; refresh token kept server-side. In Google's Testing mode only listed test users can sign in and refresh tokens expire after 7 days. Production use of these sensitive scopes would need Google's app verification.
- **AI drafting:** the model is given only the instruction, the tone and the recipient's first name, never the address. It must not invent facts (missing details become `[placeholders]`) and returns JSON only. Third-party email text is fenced as untrusted data, because emails can contain hidden instructions (prompt injection). Safety rules that matter are enforced in code (suspicious emails capped at Low, recipient never from the model, approval gate), not just in the prompt.

## Honest status
- **Real AI quality was not measured.** No AI key was available while building, so the AI output in the delivered runs is from the mock or a scripted model. The 20-example evaluation passes 20/20 with scripted good answers, which shows the pipeline and checks work. To get real results: put your key in `.env`, run `python scripts/run_evaluation.py`, and read `docs/day9_evaluation_<provider>.md`.
- **Real Google was not tested.** Login, reading and sending were tested against a fake Google (HTTP-level and in a browser). Before relying on real sending, follow `docs/day7_google_setup.md` and send a test email to your own second address.
- Gmail only; one user; no attachments.

## Quick demo script (3 minutes)
1. Start backend and frontend (README Quick start) with `LLM_PROVIDER=mock` or your key.
2. Inbox: open "Server down - need help ASAP", click **Summarize**, then **Prioritize all**. Open the "Invoice attached" email: it is flagged suspicious and ranked Low.
3. **Reply with AI**: "Say we are looking into it now". Edit, **Approve draft**, **Send (demo)…**, confirm. Check **Drafts** and the Activity log.
4. Try editing after approval: the approval is removed and Send is disabled.
5. Optional: connect your Gmail, **Allow sending**, send to your own second address.
