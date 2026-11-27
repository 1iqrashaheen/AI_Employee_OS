"""Saved drafts and the approval flow: draft -> approved -> sent.

Rules enforced here (not just in the UI):
- Nothing is sent unless its status is "approved" AND the content still matches what was approved.
- Editing an approved draft revokes the approval, so the approval always covers exactly what is sent.
- A sent draft can no longer be changed.
- Recipient must be one valid address, and the subject cannot contain line breaks (email header injection).
"""
import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from email.utils import getaddresses
from pathlib import Path
from typing import Optional

from .schemas import DraftContent, DraftCreate, DraftRecord, DraftStatus, HistoryEvent


class DraftError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


ADDRESS_RE = re.compile(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[^@\s<>\"',;]{2,}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_recipient(value: Optional[str]) -> Optional[str]:
    """Return the cleaned recipient, None if empty. Raise DraftError if it is not exactly one valid address."""
    if value is None or not value.strip():
        return None
    value = value.strip()
    if "\r" in value or "\n" in value:
        raise DraftError("Recipient cannot contain line breaks.")
    parsed = [(n, a) for n, a in getaddresses([value]) if a]
    if len(parsed) != 1:
        raise DraftError("Enter exactly one recipient address.")
    if not ADDRESS_RE.match(parsed[0][1]):
        raise DraftError(f"'{parsed[0][1]}' is not a valid email address.")
    return value


def check_subject(subject: str) -> str:
    if "\r" in subject or "\n" in subject:
        raise DraftError("Subject cannot contain line breaks.")
    if not subject.strip():
        raise DraftError("Subject cannot be empty.")
    return subject.strip()


def check_body(body: str) -> str:
    if not body.strip():
        raise DraftError("Body cannot be empty.")
    return body


def fingerprint(subject: str, body: str, recipient: Optional[str]) -> str:
    raw = json.dumps([recipient or "", subject, body], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DraftStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._sending: set[str] = set()  # drafts whose email is being delivered right now (blocks edits and double sends)

    # ---- storage -----------------------------------------------------------
    def _read(self) -> dict[str, dict]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError) as e:
            raise DraftError("Saved drafts could not be read. Check data/drafts.json.", 500) from e

    def _write(self, data: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic: a crash never leaves a half-written file

    def _load(self, data: dict, draft_id: str) -> DraftRecord:
        if draft_id not in data:
            raise DraftError("Draft not found.", 404)
        return DraftRecord.model_validate(data[draft_id])

    @staticmethod
    def _log(rec: DraftRecord, event: str) -> None:
        now = _now()
        rec.updated_at = now
        rec.history.append(HistoryEvent(at=now, event=event))

    def _not_sending(self, draft_id: str) -> None:
        if draft_id in self._sending:
            raise DraftError("This email is being sent right now. Wait a moment.", 409)

    # ---- reads -------------------------------------------------------------
    def list(self) -> list[DraftRecord]:
        with self._lock:
            records = [DraftRecord.model_validate(d) for d in self._read().values()]
        return sorted(records, key=lambda r: r.updated_at, reverse=True)

    def get(self, draft_id: str) -> DraftRecord:
        with self._lock:
            return self._load(self._read(), draft_id)

    # ---- changes -----------------------------------------------------------
    def create(self, payload: DraftCreate) -> DraftRecord:
        subject, body = check_subject(payload.subject), check_body(payload.body)
        recipient = check_recipient(payload.recipient)
        now = _now()
        rec = DraftRecord(
            id=uuid.uuid4().hex[:10],
            subject=subject,
            body=body,
            recipient=recipient,
            reply_to_email_id=payload.reply_to_email_id,
            instruction=payload.instruction,
            created_at=now,
            updated_at=now,
        )
        self._log(rec, "Draft created")
        with self._lock:
            data = self._read()
            data[rec.id] = rec.model_dump(mode="json")
            self._write(data)
        return rec

    def update(self, draft_id: str, payload: DraftContent) -> DraftRecord:
        subject, body = check_subject(payload.subject), check_body(payload.body)
        recipient = check_recipient(payload.recipient)
        with self._lock:
            data = self._read()
            rec = self._load(data, draft_id)
            self._not_sending(draft_id)
            if rec.status == DraftStatus.sent:
                raise DraftError("This draft was already sent and can no longer be changed.", 409)
            if (rec.subject, rec.body, rec.recipient) == (subject, body, recipient):
                return rec  # nothing changed: keep any approval as it is
            rec.subject, rec.body, rec.recipient = subject, body, recipient
            if rec.status == DraftStatus.approved:
                rec.status, rec.approved_at, rec.approved_hash = DraftStatus.draft, None, None
                self._log(rec, "Edited after approval: approval revoked")
            else:
                self._log(rec, "Edited")
            data[rec.id] = rec.model_dump(mode="json")
            self._write(data)
            return rec

    def approve(self, draft_id: str) -> DraftRecord:
        with self._lock:
            data = self._read()
            rec = self._load(data, draft_id)
            self._not_sending(draft_id)
            if rec.status == DraftStatus.sent:
                raise DraftError("This draft was already sent.", 409)
            if rec.status == DraftStatus.approved:
                return rec
            if check_recipient(rec.recipient) is None:
                raise DraftError("Add a recipient before approving.")
            check_subject(rec.subject)
            check_body(rec.body)
            rec.status = DraftStatus.approved
            rec.approved_at = _now()
            rec.approved_hash = fingerprint(rec.subject, rec.body, rec.recipient)
            self._log(rec, "Approved by user")
            data[rec.id] = rec.model_dump(mode="json")
            self._write(data)
            return rec

    def revoke(self, draft_id: str) -> DraftRecord:
        with self._lock:
            data = self._read()
            rec = self._load(data, draft_id)
            self._not_sending(draft_id)
            if rec.status != DraftStatus.approved:
                raise DraftError("Only an approved draft can have its approval revoked.", 409)
            rec.status, rec.approved_at, rec.approved_hash = DraftStatus.draft, None, None
            self._log(rec, "Approval revoked by user")
            data[rec.id] = rec.model_dump(mode="json")
            self._write(data)
            return rec

    @staticmethod
    def _check_sendable(rec: DraftRecord) -> None:
        if rec.status == DraftStatus.sent:
            raise DraftError("This draft was already sent.", 409)
        if rec.status != DraftStatus.approved:
            raise DraftError("Approve the draft before sending it.", 409)
        if rec.approved_hash != fingerprint(rec.subject, rec.body, rec.recipient):
            # Should be impossible, since edits revoke approval. Refuse anyway.
            raise DraftError("The draft changed after it was approved. Approve it again.", 409)

    def check_sendable(self, draft_id: str) -> DraftRecord:
        """Raise unless this draft may be sent right now (approved, unchanged, not already sending)."""
        with self._lock:
            rec = self._load(self._read(), draft_id)
            self._not_sending(draft_id)
            self._check_sendable(rec)
            return rec

    def send(self, draft_id: str) -> DraftRecord:
        """Demo send: marks an approved draft as sent. Nothing is delivered."""
        with self._lock:
            data = self._read()
            rec = self._load(data, draft_id)
            self._not_sending(draft_id)
            self._check_sendable(rec)
            rec.status = DraftStatus.sent
            rec.sent_at = _now()
            rec.delivery = "mock"
            self._log(rec, "Sent (demo mode: nothing was delivered)")
            data[rec.id] = rec.model_dump(mode="json")
            self._write(data)
            return rec

    def begin_send(self, draft_id: str) -> DraftRecord:
        """Lock an approved draft for a real send. Edits and a second send are refused until finish/abort."""
        with self._lock:
            rec = self._load(self._read(), draft_id)
            self._not_sending(draft_id)
            self._check_sendable(rec)
            self._sending.add(draft_id)
            return rec

    def finish_send(self, draft_id: str, delivery_id: Optional[str], account: Optional[str]) -> DraftRecord:
        """The email was delivered: record it. Always marks sent, because the email really went out."""
        with self._lock:
            try:
                data = self._read()
                rec = self._load(data, draft_id)
                rec.status = DraftStatus.sent
                rec.sent_at = _now()
                rec.delivery = "gmail"
                rec.delivery_id = delivery_id
                self._log(rec, f"Sent through Gmail{' from ' + account if account else ''}")
                data[rec.id] = rec.model_dump(mode="json")
                self._write(data)
                return rec
            finally:
                self._sending.discard(draft_id)

    def abort_send(self, draft_id: str, note: str) -> None:
        """The send did not complete. The draft stays approved; the reason goes into its history."""
        with self._lock:
            try:
                data = self._read()
                rec = self._load(data, draft_id)
                self._log(rec, note)
                data[rec.id] = rec.model_dump(mode="json")
                self._write(data)
            except DraftError:
                pass
            finally:
                self._sending.discard(draft_id)
