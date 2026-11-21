# Test results

Run on 2026-11-22 with Python 3.12, FastAPI, pytest (`pytest -v`), from the `task-manager/` folder.
Tests use a fixed clock (2026-11-18 12:00 UTC) and an empty store, so they give the same result at any time.

| Area | File | What is checked |
|---|---|---|
| Create, edit, assign, complete, delete, filter, sort, paging | `tests/test_tasks.py` | Required title, allowed values, reminder not after due date, unknown assignee rejected, `completed_at` set/cleared, soft delete, error shape |
| Reminders and progress | `tests/test_reminders.py` | Overdue / due soon / reminder-time kinds, order, window, completed-percent |
| Saving to a file | `tests/test_persistence.py` | Tasks, edits and deletes survive a restart; samples added once; clear error for a corrupt file |

## Result

```
============================= test session starts ==============================
platform darwin -- Python 3.12.14, pytest-9.2.0, pluggy-1.7.0 -- python3.12
cachedir: .pytest_cache
rootdir: task-manager
plugins: anyio-4.16.0
collecting ... collected 48 items

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
tests/test_tasks.py::test_naive_dates_are_treated_as_utc PASSED
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

============================== 48 passed in 0.42s ==============================
```

## Checked by hand on a running server

- Started with `TASK_MANAGER_FILE` set: 10 sample tasks loaded.
- Created a task through the API, stopped the server, started it again: the new task was still there and the total was 11 (samples were not added a second time).
- Web page (`http://localhost:8001/`) checked in a browser earlier: create, edit, tick done, delete, filters, progress card and reminders card all work. The one error message in the browser console was the deliberate test of the form's validation (HTTP 422).

## Not tested

- Connection to the shared PostgreSQL database (Hadeed's tasks API is not available yet).
- Sending reminders by email, WhatsApp or push (not built; shown in the app only).
