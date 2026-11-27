# Test results

Last run: 2026-11-25, Python 3.12, FastAPI, pytest (`pytest -v` from the `task-manager/` folder).
The tests use a fixed clock (2026-11-18 12:00 UTC), so they give the same result at any time.

| Area | File | What is checked |
|---|---|---|
| Create, edit, assign, complete, delete, filter, sort, paging | `tests/test_tasks.py` | Required title, allowed values, dates need a time zone, unknown fields rejected, empty edit rejected, reminder not after due date, unknown assignee rejected, `completed_at` set/cleared, soft delete, repeated filters, priority order, error shape |
| Reminders and progress | `tests/test_reminders.py` | Overdue / due soon / reminder-time kinds, order, window, completed-percent |
| Saving to a file | `tests/test_persistence.py` | Tasks, edits and deletes survive a restart; samples added once; clear error for a corrupt file |
| Backend mode | `tests/test_backend_mode.py` | Login and every task call passed to the shared backend with the caller's token only; backend errors passed through unchanged; reminders and progress worked out from all pages of the backend's tasks; clear errors when the backend is down or answers badly |

## Result: unit and API tests

```
============================= test session starts ==============================
platform darwin -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0 -- python3.12
cachedir: .pytest_cache
rootdir: task-manager
plugins: anyio-4.16.0
collecting ... collected 74 items

tests/test_backend_mode.py::test_health_says_which_mode PASSED
tests/test_backend_mode.py::test_login_is_passed_to_the_backend PASSED
tests/test_backend_mode.py::test_wrong_password_error_is_passed_through_unchanged PASSED
tests/test_backend_mode.py::test_every_data_route_needs_a_login[/tasks] PASSED
tests/test_backend_mode.py::test_every_data_route_needs_a_login[/tasks/reminders] PASSED
tests/test_backend_mode.py::test_every_data_route_needs_a_login[/tasks/progress] PASSED
tests/test_backend_mode.py::test_every_data_route_needs_a_login[/assignees] PASSED
tests/test_backend_mode.py::test_only_the_callers_token_is_passed_on PASSED
tests/test_backend_mode.py::test_list_passes_filters_including_repeated_ones PASSED
tests/test_backend_mode.py::test_create_goes_to_the_backend_and_returns_its_answer PASSED
tests/test_backend_mode.py::test_backend_validation_errors_reach_the_page_unchanged PASSED
tests/test_backend_mode.py::test_get_edit_and_delete_one_task PASSED
tests/test_backend_mode.py::test_missing_task_error_is_passed_through PASSED
tests/test_backend_mode.py::test_a_bad_task_id_never_reaches_the_backend PASSED
tests/test_backend_mode.py::test_reminders_are_worked_out_from_all_pages PASSED
tests/test_backend_mode.py::test_reminders_show_assignee_names_from_the_backend PASSED
tests/test_backend_mode.py::test_progress_is_worked_out_from_the_backend_tasks PASSED
tests/test_backend_mode.py::test_progress_for_one_person PASSED
tests/test_backend_mode.py::test_assignees_are_the_backends_directory PASSED
tests/test_backend_mode.py::test_dates_without_a_zone_from_the_backend_are_read_as_utc PASSED
tests/test_backend_mode.py::test_backend_down_gives_a_clear_error PASSED
tests/test_backend_mode.py::test_a_reply_that_is_not_json_gives_a_clear_error PASSED
tests/test_persistence.py::test_tasks_survive_restart PASSED
tests/test_persistence.py::test_edit_and_complete_are_saved PASSED
tests/test_persistence.py::test_deleted_task_stays_deleted_after_restart PASSED
tests/test_persistence.py::test_samples_are_added_once_not_on_every_restart PASSED
tests/test_persistence.py::test_missing_file_starts_empty_and_is_created_on_first_save PASSED
tests/test_persistence.py::test_corrupt_file_gives_a_clear_error_instead_of_silently_starting_empty PASSED
tests/test_reminders.py::test_overdue_due_soon_and_reminder_are_classified PASSED
tests/test_reminders.py::test_finished_tasks_never_appear PASSED
tests/test_reminders.py::test_task_is_listed_once_overdue_wins_over_reminder PASSED
tests/test_reminders.py::test_due_soon_window_is_adjustable_and_inclusive PASSED
tests/test_reminders.py::test_due_exactly_now_is_due_soon_not_overdue PASSED
tests/test_reminders.py::test_order_is_most_urgent_first PASSED
tests/test_reminders.py::test_reminder_messages_are_readable PASSED
tests/test_reminders.py::test_completing_a_task_removes_its_reminder PASSED
tests/test_reminders.py::test_extending_the_due_date_removes_overdue PASSED
tests/test_reminders.py::test_is_overdue_flag_on_task PASSED
tests/test_reminders.py::test_progress_on_empty_store_is_zero_not_an_error PASSED
tests/test_reminders.py::test_progress_counts_and_percent PASSED
tests/test_reminders.py::test_progress_per_person PASSED
tests/test_reminders.py::test_deleted_tasks_do_not_count PASSED
tests/test_tasks.py::test_create_task_uses_defaults PASSED
tests/test_tasks.py::test_create_with_all_fields_and_assignee_name PASSED
tests/test_tasks.py::test_create_rejects_bad_input[body0-title] PASSED
tests/test_tasks.py::test_create_rejects_bad_input[body1-title] PASSED
tests/test_tasks.py::test_create_rejects_bad_input[body2-title] PASSED
tests/test_tasks.py::test_create_rejects_bad_input[body3-priority] PASSED
tests/test_tasks.py::test_create_rejects_bad_input[body4-status] PASSED
tests/test_tasks.py::test_create_rejects_bad_input[body5-due_date] PASSED
tests/test_tasks.py::test_reminder_after_due_date_is_rejected PASSED
tests/test_tasks.py::test_unknown_assignee_is_rejected PASSED
tests/test_tasks.py::test_date_without_time_zone_is_rejected PASSED
tests/test_tasks.py::test_dates_with_an_offset_are_stored_as_utc PASSED
tests/test_tasks.py::test_unknown_fields_are_rejected PASSED
tests/test_tasks.py::test_blank_description_is_stored_as_none PASSED
tests/test_tasks.py::test_patch_with_no_fields_is_a_bad_request PASSED
tests/test_tasks.py::test_get_task_and_404s PASSED
tests/test_tasks.py::test_edit_assign_and_change_priority PASSED
tests/test_tasks.py::test_patch_only_changes_sent_fields PASSED
tests/test_tasks.py::test_patch_null_clears_a_date PASSED
tests/test_tasks.py::test_patch_cannot_blank_title_or_status PASSED
tests/test_tasks.py::test_completing_sets_completed_at_and_reopening_clears_it PASSED
tests/test_tasks.py::test_create_as_done_has_completed_at PASSED
tests/test_tasks.py::test_edit_cannot_put_reminder_after_due_date PASSED
tests/test_tasks.py::test_delete_hides_the_task PASSED
tests/test_tasks.py::test_filters PASSED
tests/test_tasks.py::test_due_before_and_after PASSED
tests/test_tasks.py::test_sort_by_priority_and_due_date_puts_missing_dates_last PASSED
tests/test_tasks.py::test_bad_sort_is_rejected PASSED
tests/test_tasks.py::test_pagination_meta PASSED
tests/test_tasks.py::test_assignees_endpoint PASSED
tests/test_tasks.py::test_unknown_route_uses_standard_error_shape PASSED
tests/test_tasks.py::test_sample_data_seeds_every_state PASSED

============================== 74 passed in 0.57s ==============================
```

The backend-mode tests use a fake backend that answers in the same shapes as Hadeed's real tasks API. To check they can fail, I removed the line that passes the token on: 12 of the 22 backend-mode tests failed, and all passed again once it was restored.

## Result: run against Hadeed's real backend

The task manager was started in backend mode (`TASK_BACKEND_URL`) and pointed at Hadeed's real backend (branch `feature/authentication`, commit 1801606), then driven through its own API with a script. Every task call below went through the task manager to the real backend, with its real login, validation, permissions and company separation.

```
PASS  sign in through the task manager
PASS  wrong password -> backend's 401 INVALID_CREDENTIALS
PASS  no token -> 401 AUTH_REQUIRED
PASS  create overdue task
PASS  create due-soon task
PASS  create reminder-only task
PASS  create done task (completed_at set by backend)
PASS  date without time zone -> backend's 422
PASS  unknown assignee -> backend's 422
PASS  unknown field -> backend's 422
PASS  list with repeated status filter, sorted by -priority (urgent first)
PASS  overdue filter
PASS  reminders: overdue, due soon, reminder
PASS  reminder shows assignee name from backend
PASS  progress: 1 done of 4 = 25%
PASS  assignees are the backend's users
PASS  complete a task (PATCH)
PASS  progress updates: 2 done of 4 = 50%, nothing overdue
PASS  empty edit -> backend's 400 NO_FIELDS_TO_UPDATE
PASS  member cannot delete a task made by someone else -> 403
PASS  admin deletes the task
PASS  deleted task -> 404 TASK_NOT_FOUND
PASS  other company sees 0 tasks
PASS  other company has no reminders
PASS  bad token -> 401

25/25 checks passed
```

How this was run, and what it does not prove:

- There is no Docker or PostgreSQL on this computer, so the backend ran on a **SQLite** database instead of PostgreSQL. Two stand-ins were needed, both only in a throw-away launcher outside the repository: SQLite had no PostgreSQL-only column types for the customers table, and SQLite returns dates without a time zone, so loaded dates were marked as UTC (PostgreSQL does this itself). The backend's own code was not changed.
- The run found one real difference that the fake backend could not: the backend's `sort=priority` puts **low first** (`-priority` puts urgent first). The task manager had it the other way round, so the page's Priority sort would have been upside down in backend mode. Fixed in the task manager and its tests, then the run above was repeated.
- Not yet tried: the same run on PostgreSQL, and any module other than the task manager talking to the backend.

## Checked by hand in the web page (browser, backend mode)

- Sign-in card shows first; a wrong password shows the backend's message and stores no token; the right one shows the tasks.
- Tasks, reminders (with assignee names), progress and the assignee list all come from the real backend.
- Create (assigned, with dates), tick done, filter, and Priority sort work; a reminder set after the due date shows the backend's message.
- An expired or bad token sends the page back to sign-in with "Your session ended"; Sign out clears the token; signing in twice does not double the assignee list.
- Standalone mode (no backend) was re-checked after the changes: sample tasks, reminders, create and edit work and no sign-in card appears.

## Not tested

- Connection to PostgreSQL (see above).
- Sending reminders by email, WhatsApp or push (not built; reminders show in the app only).
- Token refresh: the page asks you to sign in again when the token ends.
