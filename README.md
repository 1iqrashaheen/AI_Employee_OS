# AI Email Assistant

Draft emails from a short instruction, summarize and prioritize emails, and send only after a human approves. It works out of the box on 35 sample emails. Reading and sending real Gmail needs your own authorized Google connection (optional).

**What it does**
- **Draft**: type a short instruction ("Tell John the quotation for 25 laptops will be ready by Friday"), pick a tone, get an editable subject and message.
- **Summarize and prioritize**: a short summary with action items, a High/Medium/Low priority with a reason, and a *suspicious* flag for phishing or emails that try to instruct the AI.
- **Approved send**: a draft must be approved, then confirmed in a send window, before anything goes out. Real sending uses your Gmail account, only after you allow it.

## Quick start (about 5 minutes)

Needs Python 3.11+ and Node 20+.

```bash
# 1. Backend (terminal 1)
cd backend
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env          # then edit .env (see "Choose an AI" below)
uvicorn app.main:app --reload       # http://localhost:8000/docs

# 2. Frontend (terminal 2)
cd frontend
npm install
npm run dev                         # open http://localhost:3000
```

### Choose an AI
Edit `.env`:
- Try it without a key: `LLM_PROVIDER=mock`. The app and tests work, but the writing and ratings are canned placeholders.
- Real AI: set `LLM_PROVIDER` to `claude`, `openai`, `groq` or `gemini` and put your key in `LLM_API_KEY`. `LLM_MODEL` is optional (defaults are in `.env.example`).

Restart the backend after editing `.env`.

### Connect Gmail (optional)
The app never needs this to run. To read and send your own Gmail, follow `docs/day7_google_setup.md` (Google Cloud project, test user, OAuth client), put the client ID and secret in `.env`, then use the **Connect** tab. Sending is a second, separate permission (**Allow sending**). Only your own accounts, in Google's Testing mode (access lasts 7 days).

## Using the app
1. **Inbox**: pick an email, click **Summarize** or **Prioritize**, or **Prioritize all**. Use the *Sample emails / My Gmail* switch (My Gmail appears once connected).
2. Click **Reply with AI** (or open **Compose** for a new email), write an instruction, **Generate draft**, and edit the text.
3. **Approve draft**, then **Send email…** and confirm in the window that shows From, To, Subject and the full text.
4. **Drafts** lists everything with its history and an **Activity log** of approvals and sends.

The header pill shows the mode: *Demo sending* (no Gmail connected: Send only marks the draft as sent, nothing is delivered), *Sending not allowed yet* (Gmail connected for reading only), or *Live sending*.

## Safety rules (enforced in the backend, not just the buttons)
- The AI only writes text. It never sees the recipient address and cannot change who the email goes to.
- Email text is treated as untrusted data (fenced, never obeyed). A suspicious email can never be ranked above Low (a code rule, not only a prompt rule).
- Send needs an approved draft that has not changed since approval (otherwise HTTP 409). Editing an approved draft removes the approval. A draft is sent at most once, and cannot be edited while being sent.
- One valid recipient only; line breaks in To/Subject are refused (blocks header injection).
- Unclear send results (timeout) are never retried automatically: the app says to check the Gmail Sent folder.
- Login tokens stay on the backend in a local file (`data/google.token.json`, gitignored), are never sent to the browser, and are deleted (and revoked at Google) on Disconnect. Real emails are held in memory for a few minutes and are not saved. Summarize/Prioritize/Reply send the email text to the AI provider you chose.
- The activity log records recipient, subject and result, never the email body.

## API (docs at http://localhost:8000/docs)
`POST /draft`, `POST /summarize`, `POST /classify`, `GET /emails`, drafts (`POST/GET /drafts`, `PUT /drafts/{id}`, `/approve`, `/revoke-approval`, `/send`), `GET /activity`, `GET /health`, and Google login (`/auth/status`, `/auth/google/login`, `/auth/google/callback`, `/auth/google/disconnect`).

```bash
curl -X POST localhost:8000/draft -H 'content-type: application/json' \
  -d '{"instruction":"Tell John the quotation for 25 laptops will be ready by Friday","tone":"professional","recipient":"John <john@example.com>"}'
curl -X POST localhost:8000/classify -H 'content-type: application/json' -d '{"email_id":"e33"}'
```

## Tests and evaluation
```bash
cd backend
pytest -q                                  # 221 tests; fake Google and mock model, never the real internet
python scripts/run_evaluation.py --reference   # 20 examples, scripted good answers: checks the pipeline, no key needed
python scripts/run_evaluation.py           # the same 20 examples against YOUR AI (writes docs/day9_evaluation_<provider>.md)
```
Browser smoke test of the whole flow (sample mode): `e2e/smoke_test.py` (instructions inside the file). Details and the list of examples: `docs/day9_test_results.md`, `data/eval_cases.json`. Earlier example runs: `docs/day3_draft_examples.md` (drafts), `docs/day4_analysis_results.md` (35 emails; mock run, not a quality result). Screenshots: `docs/screenshots/`.

## Project layout
- `backend/app/`: `main.py` (routes), `drafting.py`, `analysis.py`, `llm.py` (provider-agnostic client), `drafts.py` (approval rules), `sender.py` (demo vs real send), `google_auth.py` and `gmail.py` (OAuth and Gmail API), `activity.py`, `evalkit.py` (evaluation checks)
- `backend/tests/`, `backend/scripts/`, `e2e/smoke_test.py`
- `frontend/`: Next.js app (`components/`: Inbox, Compose, Drafts, Connection, AppShell; `lib/api.ts`)
- `data/`: `sample_emails.json` (35 emails with hand-labelled answers), `draft_test_instructions.json`, `eval_cases.json`
- `docs/`: setup and sending guides, results, screenshots. `SUBMISSION.md`: what is submitted and its honest status.

## Known limits
- Real AI quality has not been measured by the developer (no key was available); run the evaluation with your own key.
- Gmail login, reading and sending were tested against a fake Google only. Test sending to your own second address first.
- Gmail only. Google Testing mode: 7-day access, listed test users only. No attachments, no multi-user accounts.
