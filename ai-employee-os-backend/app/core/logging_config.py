"""
Logging setup: every log line goes to the console AND to logs/app.log.

When something crashes, the 500 response contains a `request_id`.
Search for it in the log to find the full stack trace:

    Select-String -Path logs\\app.log -Pattern "a1b2c3d4e5f6" -Context 0,25

SECURITY RULE: never log passwords, tokens, or request bodies.
"""
import logging
from logging.handlers import RotatingFileHandler

from app.core.config import BASE_DIR, settings


def setup_logging() -> None:
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    # Rotates at 5 MB and keeps 3 old files, so the log never fills the disk.
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()  # avoid duplicate lines when uvicorn reloads
    root.setLevel(logging.DEBUG if settings.is_development else logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Quiet down noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)