# Task Manager and Reminders (AI Employee OS, module 13)

Create, edit, assign and complete tasks. Each task can have a due date, a priority and a reminder time.
A progress view shows how much is done, and a reminders panel shows what is overdue or due soon.

This module runs **on its own** with sample tasks. It uses the same field names, rules and response
shapes as the shared backend design, so it can be connected to the shared database later (see
[Connecting to the shared backend](#connecting-to-the-shared-backend)).

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

## Run the tests

```bash
pytest -v
```

Tests use a fixed clock and an empty store, so they give the same result at any time of day.
Latest result (48 passed) and what each test file covers: [docs/test-results.md](docs/test-results.md).

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
| GET | `/tasks` | List. Filters: `status`, `priority`, `assignee_id`, `customer_id`, `due_before`, `due_after`, `overdue=true`, `search`. Also `sort` (e.g. `due_date`, `-created_at`, `priority`), `page`, `limit` (1-100) |
| POST | `/tasks` | Create (`title` required) |
| GET | `/tasks/{id}` | Get one |
| PATCH | `/tasks/{id}` | Change only the fields you send. `status: "done"` sets `completed_at`; `null` clears a date |
| DELETE | `/tasks/{id}` | Delete (soft: hidden, not erased) |
| GET | `/tasks/reminders` | Overdue / due soon / reminder-time-reached. Optional `within_hours` (default 24) |
| GET | `/tasks/progress` | Counts and `completed_percent`. Optional `assignee_id` |

Example:

```bash
curl -X POST localhost:8001/api/v1/tasks -H 'Content-Type: application/json' \
  -d '{"title":"Follow up with John","priority":"high","due_date":"2026-11-21T09:00:00Z"}'
curl localhost:8001/api/v1/tasks/reminders
```

Rules checked by the API: title 1-200 characters; status and priority must be one of the allowed values;
the reminder cannot be after the due date; the assignee must exist; dates without a time zone are treated as UTC.

## Files

```
task-manager/
├── app/
│   ├── main.py        # FastAPI routes and error handling
│   ├── service.py     # the rules: complete, filter, reminders, progress
│   ├── store.py       # where tasks are kept (memory or JSON file) + sample data
│   ├── schemas.py     # request/response shapes and validation
│   └── static/index.html   # the web page
├── tests/             # pytest tests
└── docs/              # research.md, test-results.md, integration.md
```

## Connecting to the shared backend

Only `app/store.py` knows tasks are kept in memory. To connect to Hadeed's database:

1. Write a class with the same methods as `TaskStore` (`all`, `get`, `add`, `save`, `get_assignee`) that reads and writes the `tasks` and `users` tables.
2. Take `company_id` and the current user from the login token instead of using sample data.
3. Either keep these routes (`/tasks/reminders`, `/tasks/progress`) next to the shared backend, or compute the same numbers from `GET /tasks`.

## Limitations

- Reminders show inside the app only; no email, WhatsApp or push message is sent.
- By default tasks are kept in memory and lost when the server restarts. `TASK_MANAGER_FILE` saves them to a JSON file instead (one server only; not a replacement for the shared database).
- Assignees are four sample people and there is no login.
- `customer_id` and `record_id` are accepted but not checked (those records belong to the shared backend).
