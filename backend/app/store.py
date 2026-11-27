import json
from typing import Optional

from . import gmail
from .config import DATA_FILE
from .schemas import Email


def load_emails() -> list[Email]:
    with open(DATA_FILE, encoding="utf-8") as f:
        raw = json.load(f)
    return [Email.model_validate(item) for item in raw]


def get_email(email_id: str) -> Optional[Email]:
    """A sample email by id, or (for ids like "gmail:abc") a real email fetched from the connected Gmail.

    Gmail problems raise GoogleError, which the API turns into a clear message.
    """
    if email_id.startswith(gmail.ID_PREFIX):
        return gmail.get_message(email_id[len(gmail.ID_PREFIX):])
    return next((e for e in load_emails() if e.id == email_id), None)
