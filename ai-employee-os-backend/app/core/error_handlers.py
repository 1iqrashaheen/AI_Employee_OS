"""
Global error handlers. Every error in the API leaves through here, in ONE format:

    {
      "success": false,
      "message": "...",            safe to show to users
      "code": "SOME_CODE",         for frontend logic
      "errors": [...],             only for validation errors
      "request_id": "a1b2c3d4e5f6",
      "debug": {...}               ONLY in development, ONLY for 500 / 503
    }

How to find out what crashed (HTTP 500):
  1. Take `request_id` from the response (or the X-Request-ID header).
  2. Search for it in logs/app.log (or the console). The full stack trace is right there.
  3. In development the response itself also names the exception and the exact line of
     OUR code where it happened (`debug.location`), so you often do not need the log.
"""
import logging
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import BASE_DIR, settings
from app.core.exceptions import AppException
from app.core.middleware import get_request_id

logger = logging.getLogger("app.errors")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    errors: list[dict[str, str]] | None = None,
    debug: dict | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard error body. Every handler below uses this."""
    request_id = get_request_id(request)
    body: dict = {"success": False, "message": message, "code": code}
    if errors:
        body["errors"] = errors
    body["request_id"] = request_id
    if debug:
        body["debug"] = debug
    # Handlers for unhandled errors run outside the middleware, so set the header here too.
    response_headers = {"X-Request-ID": request_id, **(headers or {})}
    return JSONResponse(status_code=status_code, content=body, headers=response_headers)


def _debug_info(exc: BaseException) -> dict:
    """
    Development-only crash details: what failed, and WHERE in our own code.
    Frames from site-packages (libraries) are skipped, so the first entry is
    the line in YOUR code that triggered the problem.
    """
    stack: list[str] = []
    for frame in traceback.extract_tb(exc.__traceback__):
        if "site-packages" in frame.filename:
            continue
        try:
            path = str(Path(frame.filename).relative_to(BASE_DIR))
        except ValueError:
            path = frame.filename
        stack.append(f"{path}:{frame.lineno} in {frame.name}  ->  {frame.line}")

    return {
        "exception": type(exc).__name__,
        "detail": str(exc)[:500],  # may include SQL: fine in development, never in production
        "location": stack[-1] if stack else None,  # innermost frame of our code
        "stack": stack,
    }


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    """Errors we raise on purpose (wrong password, forbidden, conflict...). Not crashes."""
    logger.info(
        "[req=%s] %s %s -> %s %s: %s",
        get_request_id(request), request.method, request.url.path,
        exc.status_code, exc.code, exc.message,
    )
    return _error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        errors=exc.errors,
        headers=exc.headers,
    )


_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422: turn Pydantic's verbose errors into a simple list of {field, message}."""
    errors: list[dict[str, str]] = []
    for err in exc.errors():
        loc = list(err.get("loc", ()))
        error_type = err.get("type", "")

        if error_type == "json_invalid":
            errors.append({"field": "body", "message": "Request body is not valid JSON"})
            continue
        if loc == ["body"] and error_type == "missing":
            errors.append({"field": "request", "message": "Request body is required"})
            continue

        # Drop the leading "body"/"query"/"path" so the field reads naturally
        if loc and loc[0] in _LOCATION_PREFIXES:
            loc = loc[1:]
        field = ".".join(str(part) for part in loc) or "request"
        message = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
        errors.append({"field": field, "message": message})

    logger.info(
        "[req=%s] %s %s -> 422 VALIDATION_ERROR: %s",
        get_request_id(request), request.method, request.url.path,
        [f"{e['field']}: {e['message']}" for e in errors],
    )
    return _error_response(
        request, status_code=422, code="VALIDATION_ERROR",
        message="Validation failed", errors=errors,
    )


_HTTP_ERROR_CODES = {
    400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED", 413: "PAYLOAD_TOO_LARGE", 429: "RATE_LIMITED",
}


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Errors raised by the framework itself: unknown URL (404), wrong method (405)..."""
    if exc.status_code == 404 and exc.detail == "Not Found":
        message = f"Endpoint not found: {request.method} {request.url.path}"
    elif exc.status_code == 405:
        message = f"Method {request.method} is not allowed on {request.url.path}"
    else:
        message = str(exc.detail)

    return _error_response(
        request,
        status_code=exc.status_code,
        code=_HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR"),
        message=message,
        headers=dict(exc.headers) if exc.headers else None,  # e.g. "Allow" on a 405
    )


async def handle_database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    """503: the database cannot be reached (Docker stopped, wrong password, network)."""
    logger.error(
        "[req=%s] Database unavailable on %s %s",
        get_request_id(request), request.method, request.url.path, exc_info=exc,
    )
    return _error_response(
        request,
        status_code=503,
        code="DATABASE_UNAVAILABLE",
        message="The database is currently unavailable. Please try again shortly.",
        debug=_debug_info(exc) if settings.is_development else None,
    )


async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    500: a real bug. The full stack trace goes to the log (never to the client in
    production). The client gets a generic message and the request_id.
    """
    request_id = get_request_id(request)
    logger.error(
        "[req=%s] UNHANDLED %s on %s %s",
        request_id, type(exc).__name__, request.method, request.url.path, exc_info=exc,
    )
    return _error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred. Please share the request_id with the backend team.",
        debug=_debug_info(exc) if settings.is_development else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, handle_app_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(OperationalError, handle_database_unavailable)
    app.add_exception_handler(Exception, handle_unhandled_exception)  # catch-all, keep last