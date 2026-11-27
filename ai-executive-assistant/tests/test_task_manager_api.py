import json
import unittest
from unittest.mock import patch

from providers.api_provider import TaskManager, TaskManagerError


class TaskManagerApiTests(unittest.TestCase):
    def test_approval_reports_the_backend_error_code(self):
        for status, code in (
            (401, "AUTH_REQUIRED"),
            (401, "TOKEN_EXPIRED"),
            (403, "COMPANY_DISABLED"),
            (422, "VALIDATION_ERROR"),
        ):
            with self.subTest(code=code), patch("providers.api_provider.HTTPSConnection") as connect:
                manager = TaskManager("https://example.com/api/v1", "test-token")
                reply = connect.return_value.getresponse.return_value
                reply.status = status
                reply.read.return_value = json.dumps({"code": code}).encode()
                with self.assertRaisesRegex(TaskManagerError, f"HTTP {status}, {code}"):
                    manager.create_task({"title": "Call customer"})
                connect.return_value.request.assert_called_once()

    def test_workspace_check_uses_the_same_bearer_token_as_approval(self):
        with patch("providers.api_provider.HTTPSConnection") as connect:
            manager = TaskManager("https://example.com/api/v1", "test-token")
            reply = connect.return_value.getresponse.return_value
            reply.status = 200
            reply.read.return_value = b'{"success":true,"data":{"company":{"name":"Test workspace"}}}'
            self.assertEqual(manager.authorized_workspace(), "Test workspace")
            method, path, body, headers = connect.return_value.request.call_args.args
            self.assertEqual((method, path, body), ("GET", "/api/v1/auth/me", None))
            self.assertEqual(headers["Authorization"], "Bearer test-token")
            reply.status = 201
            reply.read.return_value = b'{"success":true,"data":{"id":"task-123"}}'
            self.assertEqual(manager.create_task({"title": "Call customer"}), "task-123")
            method, path, body, headers = connect.return_value.request.call_args.args
            self.assertEqual((method, path, json.loads(body)), ("POST", "/api/v1/tasks", {"title": "Call customer"}))
            self.assertEqual(headers["Authorization"], "Bearer test-token")
