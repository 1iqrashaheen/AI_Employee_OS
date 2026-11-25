"""
Request middleware. For every request it:
  1. gives the request a short unique ID (or reuses a valid X-Request-ID sent by the client),
  2. returns that ID in the X-Request-ID response header,
  3. logs one line:  method, path, status, duration,
  4. stops browsers caching anything under /api/v1/auth (tokens must not be cached).

The ID is what connects a 500 response seen by the frontend to the stack trace in the log.
"""
import logging
import re
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.request")

# Accept a client-supplied ID only if it is short and boring (prevents log injection).
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
_LOGIN_ATTEMPTS: dict[str, deque[datetime]] = {}


def get_request_id(request: Request) -> str:
    """Read the ID set by the middleware (used by the error handlers)."""
    return getattr(request.state, "request_id", "unknown")


def register_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID_PATTERN.match(incoming) else uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        start = time.perf_counter()
        if request.method == "POST" and request.url.path == "/api/v1/auth/login":
            from app.core.config import settings

            client_ip = request.client.host if request.client else "unknown"
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=settings.login_rate_window_seconds)
            attempts = _LOGIN_ATTEMPTS.setdefault(client_ip, deque())
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= settings.login_rate_limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "message": "Too many login attempts. Please wait before trying again.",
                        "code": "RATE_LIMITED",
                        "request_id": request_id,
                    },
                    headers={"X-Request-ID": request_id, "Retry-After": str(settings.login_rate_window_seconds)},
                )
            attempts.append(now)
        response = await call_next(request)  # an unhandled crash skips the lines below;
        duration_ms = (time.perf_counter() - start) * 1000  # the 500 handler logs it instead

        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/v1/auth"):
            response.headers["Cache-Control"] = "no-store"

        logger.info(
            "[req=%s] %s %s -> %s (%.1f ms)",
            request_id, request.method, request.url.path, response.status_code, duration_ms,
        )
        return response