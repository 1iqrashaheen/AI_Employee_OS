# AI Meeting Assistant

The Meeting Assistant takes a meeting transcript (text) or a short audio recording and returns:

- a short **summary**
- the **key decisions**
- the **action items**, each with an owner and a deadline

Relative deadlines such as "by Friday" or "next Monday" are converted into real dates (`YYYY-MM-DD`) using the meeting date.

It uses the Google **Gemini API** for both speech-to-text and summarization. No model is trained from scratch.

---

## Features

| Feature | Status |
|---|---|
| Summarize a pasted or uploaded (.txt) transcript | Done |
| Extract key decisions | Done |
| Extract action items with owner and deadline | Done |
| Convert relative deadlines to real dates | Done |
| Audio upload with speech-to-text, then summary | Done (short recordings) |
| REST API (FastAPI) | Done |
| Simple web page (Streamlit) | Done |
| Automatic retry when the AI service is busy | Done |
| Speaker identification | Not implemented (see Limitations) |
| Saving meetings to the database | Not implemented (needs the shared backend) |

---

## Tech stack

- Python 3.9+
- Gemini API (`google-genai`)
- FastAPI + Uvicorn (API)
- Streamlit (test UI)
- Pydantic (output validation)
- python-dotenv (API key)

---

## Project structure

```
meeting-assistant/
├── .env                 (your private key, NOT pushed to GitHub)
├── .env.example         (template for .env)
├── .gitignore
├── requirements.txt
├── summarize.py         (transcript -> summary, decisions, action items)
├── transcribe.py        (audio -> transcript text)
├── main.py              (FastAPI endpoints)
├── ui.py                (Streamlit page)
├── test_run.py          (quick command-line test)
├── list_models.py       (optional: list models available for your key)
├── samples/             (sample transcripts for testing)
└── README.md
```

---

## Setup

### 1. Get a Gemini API key

1. Open https://aistudio.google.com and sign in with a Google account.
2. Click **Get API key**, then **Create API key**, and copy the key.

### 2. Install

```bash
git clone <repository-url>
cd meeting-assistant
git checkout <your-branch-name>

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac / Linux

pip install -r requirements.txt
```

If the download times out on a slow connection:

```bash
pip install --default-timeout=300 --retries 15 -r requirements.txt
```

### 3. Add your API key

Copy `.env.example` to a new file named `.env` and fill it in:

```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

Never push `.env` to GitHub. It is already listed in `.gitignore`.

**About the model name:** Gemini model names change over time. If you get a `404 NOT_FOUND` error, run `python list_models.py`, pick a current `flash` or `flash-lite` model, and put its name in `GEMINI_MODEL`. No code change is needed. If you get `503 UNAVAILABLE` (service busy), the code retries automatically; if it keeps failing, try another model.

---

## How to run

Use two terminals, both inside the project folder with the virtual environment activated.

**Terminal 1: API**

```bash
python -m uvicorn main:app --reload
```

The API runs at http://127.0.0.1:8000 and interactive API docs are at http://127.0.0.1:8000/docs.

**Terminal 2: Web page**

```bash
python -m streamlit run ui.py
```

The page has two tabs: **Text transcript** (paste text or upload a .txt file) and **Audio recording** (upload an audio file).

**Quick command-line test (no API or UI needed):**

```bash
python test_run.py
```

---

## API

### `GET /`

Health check. Returns `{"status": "ok", "module": "meeting-assistant"}`.

### `POST /meetings/summarize`

Summarize a text transcript.

Request body (JSON):

```json
{
  "transcript": "Ali: Sara, please send the quotation by Friday. ...",
  "meeting_date": "2026-11-18"
}
```

`meeting_date` is optional (format `YYYY-MM-DD`). If it is missing, today's date is used.

Response:

```json
{
  "summary": "The team discussed the new client ABC Traders ...",
  "key_decisions": [
    "The maximum discount will be 5 percent.",
    "Delivery will be within 2 weeks."
  ],
  "action_items": [
    {
      "task": "Prepare and send the quotation",
      "owner": "Sara",
      "deadline": "2026-11-20"
    },
    {
      "task": "Follow up with the client by phone",
      "owner": "Usman",
      "deadline": "2026-11-23"
    }
  ]
}
```

`owner` and `deadline` are `null` when they are not mentioned in the meeting.

### `POST /meetings/summarize-audio`

Transcribe an audio file and summarize it. Sent as `multipart/form-data` with the fields `file` (the audio) and `meeting_date` (optional).

Supported formats: mp3, wav, m4a, aac, ogg, flac. Maximum size: about 18 MB (roughly 10 minutes).

Response:

```json
{
  "transcript": "Good morning everyone ...",
  "result": {
    "summary": "...",
    "key_decisions": ["..."],
    "action_items": [{ "task": "...", "owner": "...", "deadline": "..." }]
  }
}
```

### Errors

| Code | Meaning |
|---|---|
| 400 | Empty transcript or file, wrong date format, unsupported or too large audio |
| 502 | The AI service failed or was busy (the message contains details) |

---

## Integration notes for other modules

- **Task Manager (Aamna):** each item in `action_items` maps to one task: `task` becomes the title, `owner` the assignee, and `deadline` the due date (both may be `null`, so the Task Manager must accept tasks without an assignee or due date).
- **Backend (Hadeed):** a save endpoint for meetings is not connected yet. The JSON response above is the record that would be stored once the shared database API is available.
- **Frontend (Saud):** the page can call `POST /meetings/summarize` and `POST /meetings/summarize-audio` directly. The response format is fixed.

---

## Testing

Sample transcripts are in the `samples/` folder.

| Test | Input | Expected | Result |
|---|---|---|---|
| Project meeting | `sample1_project_meeting.txt` | 4 action items with correct dates | Pass |
| No owners or deadlines | `sample2_no_owners_deadlines.txt` | Owner and deadline are empty (`null`) | _fill in_ |
| No action items | `sample3_no_action_items.txt` | Empty action item list | _fill in_ |
| Sales meeting upload | `sample4_sales_meeting_upload_test.txt` | Correct owners and dates | _fill in_ |
| Audio recording | Short recorded meeting (about 1 minute) | Correct transcript, decisions, owners and dates | Partial: transcript, decisions and dates correct; one owner wrong because the same person read all the speaker parts |

Screenshots of these tests are included as testing evidence.

---

## Limitations

- **No reliable speaker identification.** If speakers are not clearly addressed by name, the AI may attribute a task to the wrong person. This showed up in the audio test, where one person read every part.
- **Short audio only.** Audio is sent in a single request, so recordings are limited to about 18 MB (around 10 minutes). Longer recordings would need to be split.
- **AI output can contain mistakes.** Summaries, owners, and deadlines should be reviewed by a person before being used.
- **Depends on an external service.** Gemini can be slow or busy, and the free tier has usage limits. The code retries a few times automatically.
- **Language.** Works best with English. Mixed or other languages may give less accurate results.
- **Not stored.** Meetings are not saved to a database yet.

## Future improvements

- Speaker identification (diarization)
- Splitting long recordings into chunks
- Saving meetings through the shared backend and database
- Sending action items directly to the Task Manager
- Better handling of Urdu and mixed-language meetings
