"""Sending an approved draft. The single place that decides demo vs real delivery.

- No Gmail connection: demo send (marks the draft sent, delivers nothing; the UI says so).
- Gmail connected without send permission: refuse and tell the user to click "Allow sending".
- Gmail connected with send permission: really send, but only an approved draft that is unchanged since approval.
"""
from . import gmail, google_auth
from .activity import ActivityLog
from .drafts import DraftError, DraftStore
from .google_auth import GoogleError
from .schemas import DraftRecord


def send_mode() -> str:
    st = google_auth.status()
    if st["reauth_required"]:
        return "reconnect"  # was connected, access expired: never fall back to demo sending
    if not st["connected"]:
        return "mock"
    return "real" if st["can_send"] else "needs_permission"


def send(store: DraftStore, log: ActivityLog, draft_id: str) -> DraftRecord:
    st = google_auth.status()
    if st["reauth_required"]:
        # Gmail access expired. A demo send here would mark the draft "sent" although nothing is delivered.
        store.check_sendable(draft_id)
        raise GoogleError("Gmail access expired. Reconnect Gmail on the Connect tab, then send.", 401, "reauth")
    if not st["connected"]:
        rec = store.send(draft_id)
        log.record("sent", rec, delivery="demo", detail="Demo mode: nothing was delivered")
        return rec

    rec = store.check_sendable(draft_id)  # approval problems are reported before permission problems
    if not st["can_send"]:
        raise GoogleError("Sending is not allowed yet. Click Allow sending on the Connect tab.", 403, "send_scope_missing")

    rec = store.begin_send(draft_id)
    try:
        result = gmail.send_message(rec.recipient or "", rec.subject, rec.body, gmail.reply_context(rec.reply_to_email_id))
    except GoogleError as e:
        if e.code == "send_unknown":
            store.abort_send(draft_id, "Gmail did not confirm the send. Check your Gmail Sent folder before sending again.")
            log.record("send_unknown", rec, delivery="gmail", detail=str(e))
        else:
            store.abort_send(draft_id, f"Send failed: {e}")
            log.record("send_failed", rec, delivery="gmail", detail=str(e), code=e.code)
        raise
    except BaseException:
        store.abort_send(draft_id, "Send failed unexpectedly. Check your Gmail Sent folder before sending again.")
        log.record("send_unknown", rec, delivery="gmail", detail="unexpected error")
        raise
    log.record("sent", rec, delivery="gmail", gmail_message_id=result.get("id"), account=st.get("email"))  # log first: the email is out
    try:
        return store.finish_send(draft_id, result.get("id"), st.get("email"))
    except DraftError as e:
        # The email WAS delivered but the draft could not be saved as sent. Keep it blocked so it cannot be sent twice.
        store.block_resend(draft_id)
        raise DraftError(
            "The email was sent, but saving that failed. Do not send it again; check your Gmail Sent folder.", 500
        ) from e
