from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Envelope for every successful response: {success, message, data}."""

    success: bool = True
    message: str = "OK"
    data: T | None = None


class FieldError(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    """Shape of every error response. Used only to document errors in Swagger."""

    success: bool = False
    message: str
    code: str
    errors: list[FieldError] | None = None
    request_id: str | None = None