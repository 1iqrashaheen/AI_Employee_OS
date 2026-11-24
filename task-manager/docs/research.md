# Task Manager and Reminders: research and design

**Owner:** Aamna (module 13). **Branch:** `aamna/task-manager`.

## What the role asks for

| Requirement | Where it is covered |
|---|---|
| Create, edit, assign, complete tasks | `POST /tasks`, `PATCH /tasks/{id}`, assignee list, checkbox/status control in the UI |
| Due dates, priorities, simple progress view | `due_date`, `priority`, `GET /tasks/progress`, progress bar and counts in the UI |
| Reminders for tasks due soon or overdue | `GET /tasks/reminders`, Reminders panel in the UI |
| Start with sample tasks, connect to shared storage later | In-memory `TaskStore` with sample data; one small class to swap for the database |

## Research: what a simple task manager needs

**Task form.** Tools such as Todoist, Trello and Asana keep the form short: a title (the only required field), then optional description, due date, priority and assignee. Everything else can be added later. I did the same: only `title` is required.

**Task states.** Most tools use three to four states. We use the four in Hadeed's schema: `todo`, `in_progress`, `done`, `cancelled`. Ticking the checkbox is a shortcut for `done`, and the date it was completed is saved automatically.

**Priority.** Four levels (`low`, `medium`, `high`, `urgent`), again matching the shared schema. Sorting by priority uses the order low, medium, high, urgent, not alphabetical (`sort=-priority` puts urgent first), the same as the shared backend. I first had it the other way round; the run against the real backend showed the difference.

**Reminders.** A real reminder system needs a background job and email/push delivery. That is more than a student demo needs, so this module shows reminders *inside the app*: when the page (or the API) is asked "what needs attention?", the answer is worked out from the current time. This is simple, has nothing that can fail silently, and is easy to test. Three kinds:

| Kind | Rule |
|---|---|
| `overdue` | task is open and its due date has passed |
| `due_soon` | task is open and due within the next 24 hours (adjustable with `within_hours`) |
| `reminder` | the task's own `remind_at` time has passed, and it is not already overdue/due soon |

Only open tasks (`todo`, `in_progress`) get reminders. A task shows once, under its most urgent kind.

**Progress.** `completed_percent = done / (all tasks - cancelled)`. Cancelled tasks are left out so cancelling does not make progress look worse.

## Decisions

1. **Same names and rules as the shared backend.** Field names, allowed values, the `{success, message, data, meta}` response and the error shape come from `ai-employee-os-backend/docs/backend-research-and-design.md`. So when Hadeed's `/tasks` API is ready, the frontend should work against it with little change.
2. **Standalone first.** Hadeed's tasks API was not built yet when this started (his plan has it on Day 6), so tasks are kept in memory. Nothing outside `app/store.py` knows that.
3. **Time is passed in, not read.** Functions take `now`, so tests can prove "overdue" and "due soon" at exact moments.
4. **Soft delete.** Deleted tasks get `deleted_at` and are hidden, as in the shared design.
5. **Plain HTML page.** One `index.html` with no build step, so it can be demonstrated immediately. The team's frontend (Saud, Next.js) will need only the API.

## Connecting to the shared backend (added 2026-11-25)

Hadeed's tasks API appeared on the `feature/authentication` branch (`/api/v1/tasks`, with login, company separation and roles). I read it and did two things.

**1. Matched the standalone rules to the real API**, so nothing changes when switching: dates must have a time zone (no more "treated as UTC"), unknown fields are rejected, an empty edit is `400 NO_FIELDS_TO_UPDATE`, a missing task is `TASK_NOT_FOUND`, `status` and `priority` filters can be repeated, and tasks carry an `assignee: {id, full_name}` object.

**2. Added backend mode** (`TASK_BACKEND_URL`). Decision: pass create/read/edit/delete and login straight to the backend with the caller's own token, rather than copy its rules into a database class here. Reasons: the backend already checks the company, permissions, assignee and customer links, so copying them would drift out of date; and only one place then writes the data. The three things the backend does not offer (reminders, progress, assignee names for the dropdown) are worked out here from its task list and user directory, with the same code and tests as standalone mode.

Differences I found and what I did about them:

| Shared backend | This module |
|---|---|
| Needs a login token on every call | Page has a sign-in form; the token stays in the browser tab; other headers (cookies) are never passed on |
| No `/tasks/reminders` or `/tasks/progress` | Worked out here from `GET /tasks` (all pages) |
| Task has `assignee` object only | Page and reminders read both `assignee` and `assignee_name` |
| User list is admin/manager only, but `/users/directory` works for every role | Assignee dropdown uses `/users/directory` |
| Members can delete only tasks they created | Backend's `403` message is shown as it is |

## Extra endpoints (not in Hadeed's list)

`GET /tasks/reminders` and `GET /tasks/progress` are specific to this module and are not in the shared backend. In backend mode this module computes them from the backend's tasks. For the final application either keep this module next to the backend or move `service.get_reminders` and `service.progress_summary` into it (they only need a task list and the time).

## Limitations and future work

- Reminders appear in the app only. No email, WhatsApp or push notification is sent.
- Tasks are in memory by default. `TASK_MANAGER_FILE` keeps them in a JSON file between restarts, but this is for demos only (one server, no sharing); the shared database replaces it.
- In standalone mode the assignees are four sample people and there is no login. In backend mode the people, login and company come from the shared backend.
- In standalone mode `customer_id` and `record_id` are accepted but not checked (customers and records live in the shared backend, which does check them in backend mode).
- In backend mode reminders and progress read all of a user's tasks on every request (up to 5,000). Fine for a demo; for real use the backend's database should compute these two.
