from app.schemas.common import ErrorResponse

_DESCRIPTIONS = {
    400: "Bad request or a business rule was violated",
    401: "Missing, invalid, expired or revoked token",
    403: "Not allowed for your role",
    404: "Not found (or it belongs to another company)",
    409: "Conflict (duplicate)",
    422: "Validation failed",
}


def error_responses(*codes: int) -> dict[int, dict]:
    """Usage: @router.get(..., responses=error_responses(401, 403, 404))"""
    return {code: {"model": ErrorResponse, "description": _DESCRIPTIONS[code]} for code in codes}