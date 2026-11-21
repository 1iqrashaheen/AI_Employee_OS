# Creating tasks from other modules

Several modules need to make follow-up tasks: the Workflow Automation (Abdul Samad), the Meeting Assistant
(action items and deadlines), the AI Executive Assistant (Iqra, "prepare task details") and the CRM.
They can all use the same call. This module has no login yet, so for now no token is needed.
After integration the shared backend's login will apply.

## Create a task

`POST /api/v1/tasks` (the task manager runs on port 8001 in the README steps)

| Field | Required | Notes |
|---|---|---|
| `title` | yes | 1-200 characters |
| `description` | no | free text |
| `priority` | no | `low`, `medium` (default), `high`, `urgent` |
| `status` | no | `todo` (default), `in_progress`, `done`, `cancelled` |
| `due_date` | no | ISO date and time, e.g. `2026-11-25T09:00:00Z`. No time zone means UTC |
| `remind_at` | no | must not be after `due_date` |
| `assignee_id` | no | must be a person from `GET /api/v1/assignees` |
| `customer_id`, `record_id` | no | link to a customer or record (not checked here) |
| `source` | no | `manual` (default), `ai_agent`, `automation`. Use `automation` for workflows and `ai_agent` for AI modules |

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
                 json={"title": "Call customer", "source": "ai_agent"})
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
