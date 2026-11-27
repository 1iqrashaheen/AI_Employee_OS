"""Read recent inbox emails from Gmail (read-only) and turn them into the app's Email shape.

Real email ids look like "gmail:<id>", so the existing summarize, classify and reply features work on them
unchanged. Fetched emails are kept in memory for 5 minutes (never written to disk) to save Gmail calls.
"""
import base64
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.message import EmailMessage
from email.header import decode_header, make_header
from typing import Optional

import httpx

from . import google_auth, http
from .analysis import to_plain_text
from .google_auth import GoogleError
from .schemas import Email

API = "https://gmail.googleapis.com/gmail/v1/users/me"
CACHE_SECONDS = 300
MAX_LIMIT = 50
MAX_BODY_CHARS = 200_000
ID_PREFIX = "gmail:"

_cache: dict[str, tuple[float, Email]] = {}


def clear_cache() -> None:
    _cache.clear()


# ---- talking to Gmail ----------------------------------------------------------

def _explain(r: httpx.Response) -> GoogleError:
    """Turn a Gmail error into a message the user can act on."""
    reason, message = "", ""
    try:
        err = r.json().get("error", {})
        message = str(err.get("message", ""))
        reason = str((err.get("errors") or [{}])[0].get("reason", ""))
    except (ValueError, AttributeError, IndexError):
        pass
    low = message.lower()
    if r.status_code == 401:
        return GoogleError("Gmail rejected the saved access. Reconnect Gmail on the Connect tab.", 401, "reauth")
    if r.status_code == 403 and (reason == "accessNotConfigured" or "has not been used" in low or "is disabled" in low):
        return GoogleError(
            "The Gmail API is turned off for your Google Cloud project. Enable it under APIs & Services > Library, wait a minute, and try again.",
            403,
            "api_disabled",
        )
    if r.status_code == 403 and reason in ("insufficientPermissions", "ACCESS_TOKEN_SCOPE_INSUFFICIENT"):
        return GoogleError("Gmail permission is missing. Disconnect, then connect again and allow reading your email.", 403, "scope_missing")
    if r.status_code == 429 or reason in ("rateLimitExceeded", "userRateLimitExceeded"):
        return GoogleError("Gmail is limiting requests. Wait a minute and try again.", 429, "rate_limited")
    if r.status_code == 404:
        return GoogleError("That email was not found in Gmail.", 404, "not_found")
    if r.status_code >= 500:
        return GoogleError("Gmail is having trouble right now. Try again shortly.", 503, "google_down")
    return GoogleError(f"Gmail returned an error ({r.status_code}){': ' + message[:150] if message else ''}.", 502, "gmail_error")


def _get(path: str, params: Optional[dict] = None) -> dict:
    r: Optional[httpx.Response] = None
    for attempt in range(2):  # a 401 usually means the token just expired: renew once and retry
        token = google_auth.get_access_token(force_refresh=attempt == 1)
        try:
            with http.client() as c:
                r = c.get(f"{API}{path}", params=params, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            raise GoogleError("Could not reach Gmail. Check your internet connection.", 503, "network")
        if r.status_code != 401:
            break
    assert r is not None
    if r.status_code == 200:
        return r.json()
    if r.status_code == 401:
        google_auth.mark_reauth_required()
    raise _explain(r)


def _post_send(payload: dict) -> dict:
    """POST messages/send. Unlike reads, an unclear failure here must NOT be retried blindly: the email may have gone out."""
    r: Optional[httpx.Response] = None
    for attempt in range(2):
        token = google_auth.get_access_token(force_refresh=attempt == 1)
        try:
            with http.client() as c:
                r = c.post(f"{API}/messages/send", json=payload, headers={"Authorization": f"Bearer {token}"})
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise GoogleError("Could not reach Gmail, so nothing was sent. Check your internet connection and try again.", 503, "network")
        except httpx.HTTPError:
            raise GoogleError(
                "Gmail did not confirm whether the email was sent. Check your Gmail Sent folder before trying again.", 502, "send_unknown"
            )
        if r.status_code != 401:  # 401 = token just expired, safe to renew and retry once (Gmail rejected it before sending)
            break
    assert r is not None
    if r.status_code == 200:
        return r.json()
    if r.status_code == 401:
        google_auth.mark_reauth_required()
        raise GoogleError("Gmail rejected the saved access. Reconnect Gmail on the Connect tab.", 401, "reauth")
    if r.status_code == 403:
        err = _explain(r)
        if err.code == "scope_missing":
            return _raise(GoogleError("Sending is not allowed yet. Click Allow sending on the Connect tab.", 403, "send_scope_missing"))
        raise err
    if r.status_code >= 500:
        raise GoogleError(
            "Gmail had a problem and did not confirm whether the email was sent. Check your Gmail Sent folder before trying again.",
            502,
            "send_unknown",
        )
    if r.status_code == 400:
        raise GoogleError("Gmail refused this message (for example an invalid recipient). Check the address and try again.", 400, "send_rejected")
    raise _explain(r)


def _raise(e: Exception):
    raise e


# ---- sending ----------------------------------------------------------------------

def build_raw_message(to: str, subject: str, body: str, in_reply_to: Optional[str] = None, references: Optional[str] = None) -> str:
    """The email as Gmail wants it: RFC 2822 text, base64url encoded. 'From' is left out; Gmail uses the signed-in account."""
    m = EmailMessage()
    try:
        m["To"] = to
        m["Subject"] = subject
        if in_reply_to:
            m["In-Reply-To"] = in_reply_to
            m["References"] = f"{references} {in_reply_to}".strip() if references else in_reply_to
        m.set_content(body, charset="utf-8")
    except ValueError as e:  # for example a line break inside a header
        raise GoogleError(f"This email cannot be sent: {e}", 422, "bad_message")
    return base64.urlsafe_b64encode(m.as_bytes()).decode("ascii")


def reply_context(email_id: Optional[str]) -> Optional[dict]:
    """For a reply to a real Gmail message: its thread and Message-ID, so the reply lands in the same conversation. Best effort."""
    if not email_id or not email_id.startswith(ID_PREFIX):
        return None
    try:
        msg = _get(
            f"/messages/{email_id[len(ID_PREFIX):]}",
            {"format": "metadata", "metadataHeaders": ["Message-ID", "References"]},
        )
    except GoogleError:
        return None  # sending the reply matters more than threading it
    headers = {h.get("name", "").lower(): h.get("value", "") for h in msg.get("payload", {}).get("headers", [])}
    if "\r" in headers.get("message-id", "") or "\n" in headers.get("message-id", ""):
        return None
    return {"thread_id": msg.get("threadId"), "message_id": headers.get("message-id") or None, "references": headers.get("references") or None}


def send_message(to: str, subject: str, body: str, reply: Optional[dict] = None) -> dict:
    """Really send one email from the connected account. Returns Gmail's {id, threadId}."""
    reply = reply or {}
    payload = {"raw": build_raw_message(to, subject, body, reply.get("message_id"), reply.get("references"))}
    if reply.get("thread_id"):
        payload["threadId"] = reply["thread_id"]
    return _post_send(payload)


# ---- parsing -------------------------------------------------------------------

def _decode_header(value: str) -> str:
    """Headers can arrive RFC 2047 encoded (=?UTF-8?B?...?=). Make them readable."""
    try:
        return str(make_header(decode_header(value))).strip()
    except Exception:
        return value.strip()


def _decode_part(part: dict) -> str:
    data = (part.get("body") or {}).get("data")
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    ctype = next((h["value"] for h in part.get("headers", []) if h.get("name", "").lower() == "content-type"), "")
    m = re.search(r'charset="?([\w.:-]+)', ctype, re.I)
    try:
        return raw.decode(m.group(1) if m else "utf-8", errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _collect(part: dict, plain: list[str], html: list[str]) -> None:
    if part.get("filename"):  # an attachment, not the message text
        return
    mime = part.get("mimeType", "")
    if mime == "text/plain":
        plain.append(_decode_part(part))
    elif mime == "text/html":
        html.append(_decode_part(part))
    for sub in part.get("parts") or []:
        _collect(sub, plain, html)


def extract_body(payload: dict) -> str:
    plain: list[str] = []
    html: list[str] = []
    _collect(payload, plain, html)
    text = "\n\n".join(p for p in plain if p.strip())
    if not text.strip():
        text = "\n\n".join(to_plain_text(h) for h in html if h.strip())
    text = to_plain_text(text) if text.strip() else ""
    return (text or "(This email has no readable text.)")[:MAX_BODY_CHARS]


def parse_message(msg: dict) -> Email:
    payload = msg.get("payload", {})
    headers = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}
    millis = int(msg.get("internalDate") or 0)
    return Email.model_validate(
        {
            "id": f"{ID_PREFIX}{msg['id']}",
            "thread_id": f"{ID_PREFIX}{msg.get('threadId', msg['id'])}",
            "from": _decode_header(headers.get("from", "")) or "(unknown sender)",
            "subject": _decode_header(headers.get("subject", "")) or "(no subject)",
            "body": extract_body(payload),
            "date": datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat(),
            "status": "unread" if "UNREAD" in msg.get("labelIds", []) else "read",
        }
    )


# ---- public ----------------------------------------------------------------------

def _store(email: Email) -> Email:
    _cache[email.id] = (time.time(), email)
    return email


def get_message(message_id: str) -> Email:
    key = f"{ID_PREFIX}{message_id}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    return _store(parse_message(_get(f"/messages/{message_id}", {"format": "full"})))


def list_inbox(limit: int = 20) -> list[Email]:
    """The most recent inbox emails, newest first. Spam and trash are excluded by Gmail."""
    limit = max(1, min(int(limit), MAX_LIMIT))
    listing = _get("/messages", {"maxResults": limit, "labelIds": "INBOX"})
    ids = [m["id"] for m in listing.get("messages", [])]
    if not ids:
        return []

    def fetch(mid: str) -> Optional[Email]:
        try:
            return _store(parse_message(_get(f"/messages/{mid}", {"format": "full"})))
        except GoogleError as e:
            if e.code == "not_found":  # deleted between the list and the fetch
                return None
            raise

    with ThreadPoolExecutor(max_workers=5) as pool:
        emails = list(pool.map(fetch, ids))
    return [e for e in emails if e is not None]
