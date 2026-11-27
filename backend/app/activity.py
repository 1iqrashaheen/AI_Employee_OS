"""Activity log: a simple, append-only record of what the app did with the user's email account.

One JSON object per line in data/activity.jsonl. It records who/what/when (recipient, subject, result),
never the email body. Writing the log must never break a send, so write errors are swallowed.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .schemas import DraftRecord

EVENTS = {
    "approved": "Draft approved",
    "approval_revoked": "Approval revoked",
    "sent": "Email sent",
    "send_failed": "Send failed",
    "send_unknown": "Send not confirmed",
    "gmail_connected": "Gmail connected (read-only)",
    "send_permission_granted": "Sending permission granted",
    "gmail_disconnected": "Gmail disconnected",
}


class ActivityLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def record(self, event: str, draft: Optional[DraftRecord] = None, **fields) -> None:
        entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event}
        if draft is not None:
            entry.update(draft_id=draft.id, to=draft.recipient, subject=draft.subject)
        entry.update({k: v for k, v in fields.items() if v is not None})
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def recent(self, limit: int = 50) -> list[dict]:
        """Newest first. A damaged line is skipped rather than hiding the whole log."""
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except (FileNotFoundError, OSError):
            return []
        out: list[dict] = []
        for line in reversed(lines):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            item["label"] = EVENTS.get(item.get("event", ""), item.get("event", ""))
            out.append(item)
            if len(out) >= limit:
                break
        return out
