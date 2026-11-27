# AI Executive Assistant

The assistant uses Gemini to draft tasks and follow-up messages from a conversation. It can create a task through the team's Task Manager after you approve the draft.

## Run the assistant

Use Python 3.11 or newer.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp -n .env.example .env
```

Set `GEMINI_API_KEY` in `.env`, then run `python main.py`. Type `history` to view the current session or `exit` to leave.

## Create tasks

1. Start the team's [Task Manager module](https://github.com/1iqrashaheen/AI_Employee_OS/tree/aamna/task-manager/task-manager). For its local mode, set `TASK_MANAGER_API_URL=http://127.0.0.1:8001/api/v1` in the assistant's `.env`. For the shared backend, set its API base URL and supply your access token in `TASK_MANAGER_TOKEN`.
2. Ask the assistant to prepare a task. For example, enter `Prepare a task to send the proposal by 2026-12-04T17:00:00+05:00`. Include an explicit time and offset for approval. If you start with a relative deadline like “Friday,” the assistant asks for the exact deadline before it can create the task.
3. Review the draft and type `approve` to submit it, or `cancel` to discard it. Any new request replaces the draft awaiting approval. A successful submission shows the Task Manager ID.

When the API URL is blank, the assistant works in draft-only mode. If a submission's outcome is uncertain, check the Task Manager list before preparing the same task again.

### Test the hosted workspace

Sign in through the hosted [Swagger login](https://ai-employee-os-hrtf.onrender.com/docs#/Authentication/login_api_v1_auth_login_post) and copy the value of `data.access_token`. Run this from the project folder on macOS:

```sh
SSL_CERT_FILE="$(.venv/bin/python -m certifi)" \
TASK_MANAGER_API_URL=https://ai-employee-os-hrtf.onrender.com/api/v1 \
  .venv/bin/python main.py --prompt-task-token
```

Paste the token at the hidden prompt. The assistant checks it and displays the workspace before accepting a draft. Task rejections show the HTTP status and the backend's error code, when available.

Run the local tests with `python -m unittest discover -s tests`.
