"""
Application exceptions.

Raise one of these anywhere in the code (services, dependencies, routers).
The handlers in error_handlers.py turn them into the standard JSON error
response, so no endpoint has to build error responses by hand:

    raise ConflictError("Email already used", code="EMAIL_ALREADY_REGISTERED")

becomes   HTTP 409  {"success": false, "code": "EMAIL_ALREADY_REGISTERED", ...}
"""


class AppException(Exception):
    """Base class. Subclasses only set the defaults below."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "Something went wrong"
    default_headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        errors: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.errors = errors
        self.headers = headers or self.default_headers
        super().__init__(self.message)


# ---- 4xx: the caller did something wrong -----------------------------------
class BadRequestError(AppException):
    status_code = 400
    code = "BAD_REQUEST"
    message = "Bad request"


class AuthenticationError(AppException):
    """401: we do not know who you are (or your token is no good)."""

    status_code = 401
    code = "UNAUTHORIZED"
    message = "Authentication required"
    default_headers = {"WWW-Authenticate": "Bearer"}


class InvalidCredentialsError(AuthenticationError):
    code = "INVALID_CREDENTIALS"
    message = "Invalid email or password"


class TokenExpiredError(AuthenticationError):
    code = "TOKEN_EXPIRED"
    message = "Token has expired. Refresh your session or log in again."


class TokenInvalidError(AuthenticationError):
    code = "TOKEN_INVALID"
    message = "Token is invalid or malformed. Please log in again."


class TokenRevokedError(AuthenticationError):
    code = "TOKEN_REVOKED"
    message = "Token is no longer valid (for example, the password was changed). Please log in again."


class PermissionDeniedError(AppException):
    """403: we know who you are, but you are not allowed to do this."""

    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action"


class AccountDisabledError(PermissionDeniedError):
    code = "ACCOUNT_DISABLED"
    message = "This account is disabled. Please contact your administrator."


class NotFoundError(AppException):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(AppException):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with existing data"

class UnprocessableError(AppException):
    """422 for rules that need the database (e.g. 'Owner must be an active user of your company'). """
    status_code = 422
    code = 'VALIDATION_ERROR'
    message = 'Validation Failed'