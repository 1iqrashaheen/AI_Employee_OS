import json
import re
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from urllib.parse import urlsplit


class TaskManagerError(Exception):
    pass


def _rejection(status: int, result: dict) -> TaskManagerError:
    code = result.get("code", "")
    if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", code):
        code = ""
    reason = f"HTTP {status}, {code}" if code else f"HTTP {status}"
    detail = {
        "AUTH_REQUIRED": "No access token reached the backend. Restart and paste the Swagger access token.",
        "TOKEN_EXPIRED": "The access token expired. Sign in again and use the new access token.",
        "TOKEN_INVALID": "Use data.access_token from Swagger, without quotes or the Bearer prefix.",
        "TOKEN_REVOKED": "This session was revoked. Sign in again and use the new access token.",
        "ACCOUNT_DISABLED": "The signed-in account is disabled.",
        "COMPANY_DISABLED": "The signed-in workspace is disabled.",
        "VALIDATION_ERROR": "Review the task details and prepare a corrected draft.",
    }.get(code, "")
    if not detail and status == 401:
        detail = "Sign in again and paste a fresh access token."
    if not detail and status == 403:
        detail = "This account is not allowed to perform the request."
    message = f"Task Manager rejected the request ({reason})."
    return TaskManagerError(f"{message} {detail}" if detail else message)


class TaskManager:
    def __init__(self, base_url: str, token: str = ""):
        url = urlsplit(base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.query
            or url.fragment
        ):
            raise ValueError("Set TASK_MANAGER_API_URL to an HTTP(S) API base URL.")
        self._host = url.hostname
        self._port = url.port
        self._base_path = url.path.rstrip("/")
        self._connection_class = HTTPSConnection if url.scheme == "https" else HTTPConnection
        self._headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def authorized_workspace(self) -> str:
        unavailable = "Task Manager did not confirm your sign-in. Check the API URL and try again."
        data = self._request("GET", "/auth/me", 200, unavailable)
        company = data.get("company")
        if isinstance(company, dict):
            name = company.get("name")
            if isinstance(name, str) and name:
                return name
        raise TaskManagerError(unavailable)

    def create_task(self, payload: dict[str, str]) -> str:
        unknown = (
            "Task Manager did not confirm creation. "
            "Check the task list before submitting the draft again."
        )
        task = self._request("POST", "/tasks", 201, unknown, payload)
        task_id = task.get("id")
        if isinstance(task_id, str) and task_id:
            return task_id
        raise TaskManagerError(unknown)

    def _request(
        self, method: str, path: str, expected_status: int, unavailable: str,
        payload: dict[str, str] | None = None,
    ) -> dict:
        connection = self._connection_class(self._host, self._port, timeout=10)
        try:
            body = json.dumps(payload) if payload is not None else None
            connection.request(method, self._base_path + path, body, self._headers)
            response = connection.getresponse()
            if 400 <= response.status < 500 and response.status != 408:
                try:
                    error = json.loads(response.read())
                except (OSError, HTTPException, ValueError):
                    error = {}
                raise _rejection(response.status, error if isinstance(error, dict) else {})
            if response.status != expected_status:
                raise TaskManagerError(unavailable)
            result = json.loads(response.read())
        except (OSError, HTTPException, ValueError) as error:
            raise TaskManagerError(unavailable) from error
        finally:
            connection.close()

        if isinstance(result, dict) and result.get("success") is True:
            data = result.get("data")
            if isinstance(data, dict):
                return data
        raise TaskManagerError(unavailable)
