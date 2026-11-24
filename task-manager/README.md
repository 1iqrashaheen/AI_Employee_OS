# Task Manager and Reminders (AI Employee OS, module 13)

Create, edit, assign and complete tasks. Each task can have a due date, a priority and a reminder time.
A progress view shows how much is done, and a reminders panel shows what is overdue or due soon.

This module has two modes:

- **Standalone** (default): runs on its own with sample tasks, no login and no database.
- **Backend mode**: uses the shared backend (Hadeed's FastAPI + PostgreSQL) for the data and its login
  (see [Using the shared backend](#using-the-shared-backend)).

Both modes use the same field names, rules and response shapes as the shared backend.

Research and design notes: [docs/research.md](docs/research.md)

## Run it

Needs Python 3.9 or newer.

```bash
cd task-manager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

- Web page: http://localhost:8001/
- API docs (Swagger): http://localhost:8001/docs

The app starts with ten sample tasks (overdue, due soon, in progress, done, cancelled).
To start empty instead: `TASK_MANAGER_SEED=0 uvicorn app.main:app --port 8001`.

To keep your tasks when the server restarts, save them to a file (samples are added only the first time):

```bash
TASK_MANAGER_FILE=tasks.json uvicorn app.main:app --port 8001
```

## Using the shared backend

1. Start Hadeed's backend as described in its own README (it listens on `http://127.0.0.1:8000`).
2. Start this module pointing at it:

```bash
TASK_BACKEND_URL=http://127.0.0.1:8000/api/v1 uvicorn app.main:app --port 8001
```

3. Open http://localhost:8001/ and sign in with an account from the shared backend.

What happens in this mode:

| What | Where it is done |
|---|---|
| Sign in, create, read, edit, delete tasks | The shared backend. This module passes the request on with **your own token**, so the backend's login, company separation, permissions and checks all apply. |
| Reminders, progress, assignee list | This module, worked out from the backend's tasks (the backend has no such endpoints). |
| Storage | Nothing is stored here, and no password or token is kept by this server. The page keeps the token in the browser tab only. |

If the backend is not running, the page shows "The shared backend could not be reached" (error code `BACKEND_UNAVAILABLE`).
Sign-out forgets the token in this browser; an expired token sends you back to the sign-in form.

## Run the tests

```bash
pytest -v
```

Tests use a fixed clock and an empty store, so they give the same result at any time of day.
Latest result (74 passed) and what each test file covers: [docs/test-results.md](docs/test-results.md).

Other modules that want to create tasks (workflow, meeting assistant, executive assistant): [docs/integration.md](docs/integration.md).

## What you can do in the web page

| Control | What it does |
|---|---|
| **+ New task** | Opens the form: title (required), description, priority, status, assignee, due date, reminder time |
| Checkbox | Marks the task done (and un-ticks to re-open it) |
| Status dropdown | Moves a task between to do / in progress / done / cancelled |
| **Edit** / **Delete** | Edit all fields in the form, or delete the task (asks first) |
| Search, status, priority, assignee, sort, "overdue only" | Filter and order the list |
| **Progress** card | Percent done, counts by status, number overdue and due soon |
| **Reminders** card | Overdue, due-soon and reminder-time-reached tasks, most urgent first |

## API

Base path `/api/v1`. Responses use `{ "success", "message", "data", "meta" }`;
errors use `{ "success": false, "message", "code", "errors": [{ "field", "message" }] }`.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Check the app is running |
| GET | `/assignees` | Sample people tasks can be assigned to |
| GET | `/tasks` | List. Filters: `status`, `priority` (repeat for several, e.g. `?status=todo&status=in_progress`), `assignee_id`, `customer_id`, `due_before`, `due_after`, `overdue=true`, `search`. Also `sort` (e.g. `due_date`, `-created_at`, `priority`), `page`, `limit` (1-100) |
| POST | `/tasks` | Create (`title` required) |
| GET | `/tasks/{id}` | Get one |
| PATCH | `/tasks/{id}` | Change only the fields you send (at least one). `status: "done"` sets `completed_at`; `null` clears a date |
| DELETE | `/tasks/{id}` | Delete (soft: hidden, not erased) |
| GET | `/tasks/reminders` | Overdue / due soon / reminder-time-reached. Optional `within_hours` (default 24) |
| GET | `/tasks/progress` | Counts and `completed_percent`. Optional `assignee_id` |

Example:

```bash
curl -X POST localhost:8001/api/v1/tasks -H 'Content-Type: application/json' \
  -d '{"title":"Follow up with John","priority":"high","due_date":"2026-11-21T09:00:00Z"}'
curl localhost:8001/api/v1/tasks/reminders
```

Rules checked by the API (the same as the shared backend): title 1-200 characters; description up to 5000;
status and priority must be one of the allowed values; the reminder cannot be after the due date; the assignee
must exist; **dates must include a time zone** (`...Z` or `+05:00`, a bare local time is rejected); unknown fields
are rejected; an empty edit is rejected (`NO_FIELDS_TO_UPDATE`). A missing task is `TASK_NOT_FOUND` (404).
In backend mode (`TASK_BACKEND_URL`) these checks are done by the shared backend, and the API also has
`POST /auth/login` and `GET /auth/me`, which are passed on to it.

## Files

```
task-manager/
├── app/
│   ├── main.py        # FastAPI routes and error handling (both modes)
│   ├── backend.py     # backend mode: talks to the shared backend
│   ├── service.py     # the rules: complete, filter, reminders, progress
│   ├── store.py       # where tasks are kept (memory or JSON file) + sample data
│   ├── schemas.py     # request/response shapes and validation
│   └── static/index.html   # the web page
├── tests/             # pytest tests
└── docs/              # research.md, test-results.md, integration.md
```

## Joining the final application

Backend mode is the connection to the shared backend, so no database code lives in this module.
For the merged application there are two options for the two features the backend does not have:

1. Keep this module running next to the backend (as in backend mode) and call its `/tasks/reminders` and `/tasks/progress`.
2. Move `service.get_reminders` and `service.progress_summary` into the backend. They only need a list of tasks (`store.all()`) and the current time, so the move is small.

The web page here is a working demonstration; Saud's frontend can call the same endpoints.

## Limitations

- Reminders show inside the app only; no email, WhatsApp or push message is sent.
- In standalone mode tasks are kept in memory and lost when the server restarts. `TASK_MANAGER_FILE` saves them to a JSON file instead (one server only; not a replacement for the shared database).
- In standalone mode the assignees are four sample people and there is no login.
- In backend mode reminders and progress read all of the user's tasks from the backend on every request (up to 5,000). That is fine for a demo; a large company would need these two numbers computed by the backend's database.
- In backend mode the sign-in token lasts as long as the backend allows (60 minutes by default). There is no automatic refresh: after it ends the page asks you to sign in again.
- `customer_id` and `record_id` are accepted but not checked (those records belong to the shared backend).
