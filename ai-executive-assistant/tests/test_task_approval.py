import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from google.genai import types

import main
from providers.api_provider import TaskManagerError


DUE_DATE = "2026-12-04T17:00:00+05:00"


def draft_response(due_date: str) -> SimpleNamespace:
    return SimpleNamespace(
        text=None,
        function_calls=[
            types.FunctionCall(
                name="prepare_task", args={"title": "Send proposal", "due_date": due_date}
            )
        ],
    )


class TaskApprovalTests(unittest.TestCase):
    def run_conversation(self, instructions, model_responses, submission_error=None, api_url=None):
        if api_url is None:
            api_url = "http://127.0.0.1:8001/api/v1"
        client = MagicMock()
        client.__enter__.return_value = client
        client.models.generate_content.side_effect = model_responses
        output = io.StringIO()
        with (
            patch.dict("os.environ", {"TASK_MANAGER_API_URL": api_url, "TASK_MANAGER_TOKEN": ""}),
            patch("main.create_gemini_client", return_value=client),
            patch("main.TaskManager") as manager,
            patch("builtins.input", side_effect=[*instructions, "exit"]),
            redirect_stdout(output),
        ):
            submit = manager.return_value.create_task
            submit.return_value = "task-123"
            submit.side_effect = submission_error
            main.main()
        return output.getvalue(), submit

    def test_approval_creates_one_task_and_shows_its_id_in_history(self):
        output, submit = self.run_conversation(
            ["Prepare a task", "approve", "approve", "history"], [draft_response(DUE_DATE)]
        )
        submit.assert_called_once_with(
            {"title": "Send proposal", "due_date": DUE_DATE, "source": "ai_agent"}
        )
        self.assertLess(output.index("Task draft:"), output.index("Task created:"))
        self.assertIn("There is no task draft ready to approve.", output)
        self.assertIn("Assistant: Task created: Send proposal (ID: task-123)", output)

    def test_cancel_and_model_text_cannot_authorize_a_write(self):
        output, submit = self.run_conversation(
            ["Prepare a task", "cancel", "Create it", "approve"],
            [draft_response(DUE_DATE), SimpleNamespace(function_calls=[], text="Type approve.")],
        )
        submit.assert_not_called()
        self.assertIn("Task draft cancelled.", output)
        self.assertIn("There is no task draft ready to approve.", output)

    def test_missing_timezone_or_relative_date_disarms_the_previous_draft(self):
        for due_date in ("Friday", "2026-12-04T17:00:00"):
            with self.subTest(due_date=due_date):
                output, submit = self.run_conversation(
                    ["Prepare a task", "Change the deadline", "approve"],
                    [draft_response(DUE_DATE), draft_response(due_date)],
                )
                submit.assert_not_called()
                self.assertIn("What date, time, and timezone should I use?", output)

    def test_unknown_outcome_does_not_retry_the_approved_request(self):
        output, submit = self.run_conversation(
            ["Prepare a task", "approve", "approve"],
            [draft_response(DUE_DATE)],
            TaskManagerError("Check the task list before submitting the draft again."),
        )
        submit.assert_called_once()
        self.assertIn("Check the task list", output)
        self.assertNotIn("Task created:", output)

    def test_draft_only_mode_still_displays_relative_deadlines(self):
        output, submit = self.run_conversation(
            ["Prepare a task"], [draft_response("Friday")], api_url=""
        )
        submit.assert_not_called()
        self.assertIn("Task draft: Send proposal (due Friday)", output)
        self.assertNotIn("Type 'approve'", output)
