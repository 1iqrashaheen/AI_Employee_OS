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
    if not st["connected"]:
        return "mock"
    return "real" if st["can_send"] else "needs_permission"


def send(store: DraftStore, log: ActivityLog, draft_id: str) -> DraftRecord:
    st = google_auth.status()
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
    done = store.finish_send(draft_id, result.get("id"), st.get("email"))
    log.record("sent", done, delivery="gmail", gmail_message_id=result.get("id"), account=st.get("email"))
    return done
