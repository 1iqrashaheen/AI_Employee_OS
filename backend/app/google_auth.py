"""Google sign-in for the Gmail connection (OAuth 2.0 authorization-code flow with PKCE).

Design rules:
- Ask only for what is needed now: read-only Gmail access plus the account's email address.
  The send permission is requested separately and only when the user clicks "Allow sending" (Day 8).
- Tokens live in one file with owner-only permissions (0600), gitignored. No API response ever contains a token.
- `state` (one-time, expiring) blocks forged callbacks; PKCE blocks a stolen authorization code.
- In Google's Testing mode, refresh tokens expire after 7 days. When that happens we keep the account's
  email, drop the dead tokens, and ask the user to reconnect, instead of failing mysteriously.
"""
import base64
import hashlib
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx

from . import config, http

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SCOPE_READ = "https://www.googleapis.com/auth/gmail.readonly"
SCOPE_SEND = "https://www.googleapis.com/auth/gmail.send"
LOGIN_SCOPES = ["openid", "email", SCOPE_READ]
SEND_LOGIN_SCOPES = LOGIN_SCOPES + [SCOPE_SEND]

STATE_TTL_SECONDS = 600
EXPIRY_MARGIN_SECONDS = 60


class GoogleError(Exception):
    """A problem with the Google connection that is safe to show to the user."""

    def __init__(self, message: str, status_code: int = 400, code: str = "error"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


_pending: dict[str, tuple[str, float, bool]] = {}  # state -> (PKCE verifier, expiry time, send permission requested)
_lock = threading.Lock()


# ---- configuration ---------------------------------------------------------------

def missing_settings() -> list[str]:
    return [n for n, v in (("GOOGLE_CLIENT_ID", config.GOOGLE_CLIENT_ID), ("GOOGLE_CLIENT_SECRET", config.GOOGLE_CLIENT_SECRET)) if not v]


def is_configured() -> bool:
    return not missing_settings()


# ---- token file -----------------------------------------------------------------

def _read() -> dict:
    try:
        return json.loads(config.GOOGLE_TOKEN_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError):
        return {}  # a damaged file is treated as "not connected"; the user can simply reconnect


def _write(data: dict) -> None:
    path = config.GOOGLE_TOKEN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # owner-only from the start
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _delete() -> None:
    try:
        config.GOOGLE_TOKEN_FILE.unlink()
    except FileNotFoundError:
        pass


def _mark_reauth(data: dict) -> None:
    """Keep only who it was, so the screen can say 'reconnect x@gmail.com'."""
    _write({"email": data.get("email"), "reauth_required": True})


def mark_reauth_required() -> None:
    _mark_reauth(_read())


# ---- status ----------------------------------------------------------------------

def status() -> dict:
    data = _read()
    reauth = bool(data.get("reauth_required"))
    connected = bool(data.get("access_token") or data.get("refresh_token")) and not reauth
    scopes = data.get("scope", "").split() if connected else []
    return {
        "configured": is_configured(),
        "missing": missing_settings(),
        "connected": connected,
        "email": data.get("email"),
        "scopes": scopes,
        "can_read": SCOPE_READ in scopes,
        "can_send": SCOPE_SEND in scopes,
        "reauth_required": reauth,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
    }


# ---- login -------------------------------------------------------------------------

def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def start_login(allow_send: bool = False) -> str:
    """Return the Google URL to send the user to. allow_send=True also asks for the permission to send email."""
    if not is_configured():
        raise GoogleError(
            "Google sign-in is not set up yet. Add " + " and ".join(missing_settings()) + " to .env and restart the backend.",
            503,
            "not_configured",
        )
    now = time.time()
    with _lock:
        for s in [s for s, (_, exp, _w) in _pending.items() if exp < now]:
            del _pending[s]
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        _pending[state] = (verifier, now + STATE_TTL_SECONDS, allow_send)
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SEND_LOGIN_SCOPES if allow_send else LOGIN_SCOPES),
        "access_type": "offline",  # gives a refresh token so the connection outlives one hour
        "prompt": "consent",  # makes Google return that refresh token every time
        "include_granted_scopes": "true",  # lets Day 8 add the send permission later
        "state": state,
        "code_challenge": _b64url(hashlib.sha256(verifier.encode("ascii")).digest()),
        "code_challenge_method": "S256",
    }
    hint = _read().get("email")
    if allow_send and hint and "@" in hint:
        params["login_hint"] = hint  # pre-selects the account that is already connected
    return f"{AUTH_URL}?{urlencode(params)}"


def _email_from_id_token(id_token: Optional[str]) -> Optional[str]:
    # The token came straight from Google over TLS, so reading it without re-verifying the signature is fine.
    try:
        payload = id_token.split(".")[1]  # type: ignore[union-attr]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("email")
    except Exception:
        return None


def _google_message(r: httpx.Response) -> str:
    try:
        body = r.json()
        return str(body.get("error_description") or body.get("error") or "")[:200]
    except ValueError:
        return ""


def finish_login(code: str, state: str) -> tuple[str, bool]:
    """Trade the one-time code for tokens and save them. Returns (email address, whether sending was requested)."""
    with _lock:
        entry = _pending.pop(state, None)  # one-time use
    if entry is None or entry[1] < time.time():
        raise GoogleError("The sign-in link expired or was not started here. Please try connecting again.", 400, "bad_state")
    verifier, _, wants_send = entry
    try:
        with http.client() as c:
            r = c.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": config.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
    except httpx.HTTPError:
        raise GoogleError("Could not reach Google to finish signing in. Check your internet connection.", 503, "network")
    if r.status_code != 200:
        detail = _google_message(r)
        raise GoogleError(f"Google rejected the sign-in{': ' + detail if detail else ''}.", 400, "token_rejected")

    tok = r.json()
    scopes = tok.get("scope", "").split()
    if SCOPE_READ not in scopes:
        raise GoogleError(
            "Gmail access was not granted. On the Google screen, tick the box that allows reading your email, then try again.",
            400,
            "scope_missing",
        )
    if wants_send and SCOPE_SEND not in scopes:
        # Google lets people untick single permissions. Keep the existing (read-only) connection untouched.
        raise GoogleError(
            "Sending was not allowed on the Google screen, so the app still can only read. Try again and keep the box for sending email ticked.",
            400,
            "send_scope_missing",
        )
    if not tok.get("refresh_token"):
        raise GoogleError(
            "Google did not return a long-lived token. Remove this app at myaccount.google.com/permissions, then connect again.",
            400,
            "no_refresh_token",
        )
    email = _email_from_id_token(tok.get("id_token")) or "your Google account"
    _write(
        {
            "access_token": tok["access_token"],
            "refresh_token": tok["refresh_token"],
            "expires_at": time.time() + int(tok.get("expires_in", 3600)),
            "scope": tok.get("scope", ""),
            "email": email,
            "connected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    )
    return email, wants_send


# ---- using the tokens --------------------------------------------------------------

def _refresh(data: dict) -> dict:
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        _mark_reauth(data)
        raise GoogleError("Google access expired. Reconnect Gmail on the Connect tab.", 401, "reauth")
    try:
        with http.client() as c:
            r = c.post(
                TOKEN_URL,
                data={
                    "client_id": config.GOOGLE_CLIENT_ID,
                    "client_secret": config.GOOGLE_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
    except httpx.HTTPError:
        raise GoogleError("Could not reach Google to renew access. Try again in a moment.", 503, "network")
    if r.status_code == 200:
        tok = r.json()
        data = {
            **data,
            "access_token": tok["access_token"],
            "expires_at": time.time() + int(tok.get("expires_in", 3600)),
            "scope": tok.get("scope", data.get("scope", "")),
        }
        _write(data)
        return data
    if r.status_code in (400, 401):  # invalid_grant: revoked, or the 7-day Testing-mode limit
        _mark_reauth(data)
        raise GoogleError(
            "Google access expired or was revoked (in Google's Testing mode it lasts 7 days). Reconnect Gmail on the Connect tab.",
            401,
            "reauth",
        )
    raise GoogleError("Google could not renew access right now. Try again shortly.", 503, "google_down")


def get_access_token(force_refresh: bool = False) -> str:
    """A valid access token, renewed automatically when it is about to expire."""
    with _lock:
        data = _read()
        if data.get("reauth_required"):
            raise GoogleError("Google access expired. Reconnect Gmail on the Connect tab.", 401, "reauth")
        if not (data.get("access_token") or data.get("refresh_token")):
            raise GoogleError("Gmail is not connected. Connect it on the Connect tab.", 401, "not_connected")
        fresh = data.get("access_token") and data.get("expires_at", 0) - EXPIRY_MARGIN_SECONDS > time.time()
        if fresh and not force_refresh:
            return data["access_token"]
        return _refresh(data)["access_token"]


def disconnect() -> bool:
    """Revoke the grant at Google (best effort) and forget the tokens. Returns True if Google confirmed."""
    data = _read()
    token = data.get("refresh_token") or data.get("access_token")
    revoked = False
    if token:
        try:
            with http.client() as c:
                revoked = c.post(REVOKE_URL, data={"token": token}).status_code == 200
        except httpx.HTTPError:
            revoked = False
    _delete()  # forget locally even if Google could not be reached
    return revoked
