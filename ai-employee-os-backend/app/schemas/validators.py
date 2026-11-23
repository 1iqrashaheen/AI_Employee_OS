"""Reuseable input rules shared by every request schema."""

import re
from typing import Annotated
from pydantic import BaseModel, StringConstraints

# A person's name: trimmed, 2 to 150 characters.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]

_PHONE_PATTERN = re.compile(r"^[0-9+\-() ]{7,20}$")


def normalize_email(value):
    """Required email: trim and lowercase ('Ali@Acme.com ' -> 'ali@acme.com')."""
    return value.strip().lower() if isinstance(value, str) else value


def normalize_optional_email(value):
    """Optional email: like normalize_email, but an empty string means 'no email'."""
    if isinstance(value, str):
        return value.strip().lower() or None
    return value


def check_password_strength(value: str) -> str:
    """Rules for NEW passwords. bcrypt only reads 72 BYTES, so longer is rejected, not cut."""
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes long")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one number")
    return value


def check_phone(value: str | None) -> str | None:
    """Digits, +, -, spaces and brackets only; 7 to 20 characters. Empty means 'no phone'."""
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    if not _PHONE_PATTERN.match(value):
        raise ValueError("Phone must be 7 to 20 characters: digits, +, -, spaces and brackets only")
    return value


def strip_or_none(value: str | None) -> str | None:
    """Trim text; an empty string becomes None."""
    if value is None:
        return None
    return value.strip() or None


def lowercase_or_none(value: str | None) -> str | None:
    cleaned = strip_or_none(value)
    return cleaned.lower() if cleaned else None


def clean_tags(value: list[str] | None) -> list[str] | None:
    """Trim, lowercase, drop empties and duplicates; at most 20 tags of at most 50 characters."""
    if value is None:
        return None
    cleaned: list[str] = []
    for tag in value:
        tag = tag.strip().lower()
        if not tag:
            continue
        if len(tag) > 50:
            raise ValueError("Each tag must be at most 50 characters")
        if tag not in cleaned:
            cleaned.append(tag)
    if len(cleaned) > 20:
        raise ValueError("At most 20 tags are allowed")
    return cleaned


def forbid_nulls(model: BaseModel, fields: tuple[str, ...]) -> None:
    """PATCH rule: a required field may be left out, but not explicitly set to null."""
    for name in fields:
        if name in model.model_fields_set and getattr(model, name) is None:
            raise ValueError(f"{name} cannot be null")