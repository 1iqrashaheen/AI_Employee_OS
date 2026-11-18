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

**Priority.** Four levels (`low`, `medium`, `high`, `urgent`), again matching the shared schema. Sorting by priority uses the order urgent, high, medium, low, not alphabetical.

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

## Extra endpoints (not in Hadeed's list)

`GET /tasks/reminders` and `GET /tasks/progress` are specific to this module. If the shared backend does not add them, the same numbers can be computed in the frontend from `GET /tasks`, or this module's `service.py` can run next to the shared backend.

## Limitations and future work

- Reminders appear in the app only. No email, WhatsApp or push notification is sent.
- Tasks are lost when the server restarts (in memory) until the shared database is connected.
- Assignees are four sample people, and there is no login. After integration, the user and company come from the login token.
- `customer_id` and `record_id` are accepted but not checked, because customers and records live in the shared backend.
