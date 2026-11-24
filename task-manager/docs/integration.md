# Creating tasks from other modules

Several modules need to make follow-up tasks: the Workflow Automation (Abdul Samad), the Meeting Assistant
(action items and deadlines), the AI Executive Assistant (Iqra, "prepare task details") and the CRM.
They can all use the same call, and **it is the same call as the shared backend's** `POST /api/v1/tasks`
(same fields, same rules, same answers). Code written against this module works unchanged against the
shared backend, which needs a login token:

| Mode | Base URL | Token |
|---|---|---|
| Standalone (README steps) | `http://localhost:8001/api/v1` | not needed |
| Backend mode (`TASK_BACKEND_URL` set) or the shared backend itself | `http://localhost:8001/api/v1` or `http://127.0.0.1:8000/api/v1` | `Authorization: Bearer <access_token>` from `POST /auth/login` |

Create calls need no changes between the two except for adding the header.

## Create a task

`POST /api/v1/tasks` (the task manager runs on port 8001 in the README steps)

| Field | Required | Notes |
|---|---|---|
| `title` | yes | 1-200 characters |
| `description` | no | free text |
| `priority` | no | `low`, `medium` (default), `high`, `urgent` |
| `status` | no | `todo` (default), `in_progress`, `done`, `cancelled` |
| `due_date` | no | ISO date and time **with a time zone**: `2026-11-25T09:00:00Z` or `2026-11-25T09:00:00+05:00`. A bare `2026-11-25T09:00:00` is rejected (422) |
| `remind_at` | no | must not be after `due_date` |
| `assignee_id` | no | must be a person from `GET /api/v1/assignees` |
| `customer_id`, `record_id` | no | link to a customer or record. The shared backend checks they exist in your company; standalone mode does not check |
| `source` | no | `manual` (default), `ai_agent`, `automation`. Use `automation` for workflows and `ai_agent` for AI modules |

Any other field is rejected (422), and `completed_at` cannot be set by clients. The backend fills `created_by` and the company from the token.

A good response is `201` with `{ "success": true, "data": { "id": "...", ... } }`.
A bad request is `422` with `{ "success": false, "code": "VALIDATION_ERROR", "errors": [{ "field", "message" }] }`.

## Examples

Workflow: after a quotation is sent, make a follow-up task in 3 days.

```bash
curl -X POST localhost:8001/api/v1/tasks -H 'Content-Type: application/json' -d '{
  "title": "Follow up with John about the quotation",
  "priority": "medium",
  "due_date": "2026-11-25T09:00:00Z",
  "source": "automation"
}'
```

Meeting assistant: an action item with a deadline found in the meeting.

```bash
curl -X POST localhost:8001/api/v1/tasks -H 'Content-Type: application/json' -d '{
  "title": "Send the updated price list",
  "description": "Agreed in the Monday sales meeting.",
  "priority": "high",
  "due_date": "2026-11-24T17:00:00Z",
  "remind_at": "2026-11-24T09:00:00Z",
  "source": "ai_agent"
}'
```

Python:

```python
import httpx

res = httpx.post("http://localhost:8001/api/v1/tasks",
                 json={"title": "Call customer", "source": "ai_agent"},
                 headers={"Authorization": f"Bearer {token}"})  # leave the header out in standalone mode
res.raise_for_status()          # do not ignore failures
task_id = res.json()["data"]["id"]
```

## Other calls that may help

| Need | Call |
|---|---|
| Mark a task done | `PATCH /api/v1/tasks/{id}` with `{"status": "done"}` |
| Show what is overdue or due soon | `GET /api/v1/tasks/reminders` |
| Show a progress summary | `GET /api/v1/tasks/progress` |
| List a customer's tasks | `GET /api/v1/tasks?customer_id=...` |

Full list and field details: the API table in the [README](../README.md), or `/docs` on the running server.
