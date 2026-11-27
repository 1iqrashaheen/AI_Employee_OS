from typing import Literal, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from . import config, gmail, google_auth, llm, sender
from .activity import ActivityLog
from .analysis import EmptyEmailError, classify_email, summarize_email
from .drafting import draft_email
from .drafts import DraftError, DraftStore
from .google_auth import GoogleError
from .schemas import (
    AnalyzeRequest,
    ClassifyResult,
    DraftContent,
    DraftCreate,
    DraftRecord,
    DraftRequest,
    DraftResponse,
    Email,
    SummaryResult,
)
from .store import get_email, load_emails

app = FastAPI(title="AI Email Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def reject_foreign_origins(request: Request, call_next):
    """Another website must not be able to trigger approve/send/disconnect through the user's browser."""
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin != config.FRONTEND_ORIGIN.rstrip("/"):
        return JSONResponse(status_code=403, content={"detail": "Requests from this origin are not allowed."})
    return await call_next(request)


@app.exception_handler(GoogleError)
async def google_error_handler(_: Request, exc: GoogleError):
    """Gmail and Google sign-in problems become a clear message the screen can show."""
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc), "code": exc.code})


@app.get("/health")
def health():
    connected = google_auth.status()["connected"]
    return {
        "status": "ok",
        "mode": "gmail" if connected else "sample",
        "google_configured": google_auth.is_configured(),
        "google_connected": connected,
        "llm_configured": llm.is_configured(),
        "send_mode": sender.send_mode(),  # mock (demo) | needs_permission (connected, read-only) | real
    }


@app.post("/draft", response_model=DraftResponse)
def create_draft(req: DraftRequest):
    """Turn a short instruction into a draft. Never sends anything."""
    original = None
    if req.reply_to_email_id:
        original = get_email(req.reply_to_email_id)
        if original is None:
            raise HTTPException(status_code=404, detail="Email to reply to was not found")
    try:
        return draft_email(req, original)
    except llm.LLMError as e:
        raise HTTPException(status_code=503, detail=str(e))


def _resolve(req: AnalyzeRequest) -> AnalyzeRequest:
    """If an email_id is given, load that stored email; otherwise use the pasted text."""
    if req.email_id:
        email = get_email(req.email_id)
        if email is None:
            raise HTTPException(status_code=404, detail="Email not found")
        return AnalyzeRequest(subject=email.subject, body=email.body, sender=email.sender)
    return req


def _run(fn, req: AnalyzeRequest):
    try:
        return fn(_resolve(req))
    except EmptyEmailError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except llm.LLMError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/summarize", response_model=SummaryResult)
def summarize(req: AnalyzeRequest):
    """Short summary plus action items. Read-only: changes nothing."""
    return _run(summarize_email, req)


@app.post("/classify", response_model=ClassifyResult)
def classify(req: AnalyzeRequest):
    """Priority (High/Medium/Low), category, reason, and a suspicious flag. Read-only."""
    return _run(classify_email, req)


store = DraftStore(config.DRAFTS_FILE)
activity = ActivityLog(config.ACTIVITY_FILE)


def _call(fn, *args):
    try:
        return fn(*args)
    except DraftError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@app.get("/drafts", response_model=list[DraftRecord])
def list_drafts():
    return _call(lambda: store.list())


@app.post("/drafts", response_model=DraftRecord)
def save_draft(payload: DraftCreate):
    """Save a draft (for example the one /draft just generated). Does not send anything."""
    if payload.reply_to_email_id and get_email(payload.reply_to_email_id) is None:
        raise HTTPException(status_code=404, detail="Email to reply to was not found")
    return _call(lambda: store.create(payload))


@app.get("/drafts/{draft_id}", response_model=DraftRecord)
def read_draft(draft_id: str):
    return _call(lambda: store.get(draft_id))


@app.put("/drafts/{draft_id}", response_model=DraftRecord)
def edit_draft(draft_id: str, payload: DraftContent):
    """Edit a draft. Editing an approved draft revokes its approval."""
    return _call(lambda: store.update(draft_id, payload))


@app.post("/drafts/{draft_id}/approve", response_model=DraftRecord)
def approve_draft(draft_id: str):
    """The explicit human approval step. Needs a valid recipient, subject and body."""
    rec = _call(lambda: store.approve(draft_id))
    activity.record("approved", rec)
    return rec


@app.post("/drafts/{draft_id}/revoke-approval", response_model=DraftRecord)
def revoke_draft_approval(draft_id: str):
    rec = _call(lambda: store.revoke(draft_id))
    activity.record("approval_revoked", rec)
    return rec


@app.post("/drafts/{draft_id}/send", response_model=DraftRecord)
def send_draft(draft_id: str):
    """Send an approved draft. Refuses anything that is not approved. Demo when no Gmail is connected."""
    return _call(lambda: sender.send(store, activity, draft_id))


@app.get("/activity")
def read_activity(limit: int = Query(50, ge=1, le=200)):
    """What the app did with your email account (approvals, sends, connections). Never includes email bodies."""
    return activity.recent(limit)


@app.get("/auth/status")
def auth_status():
    """Is Google set up, and is an account connected? Never includes any token."""
    return google_auth.status()


@app.post("/auth/google/login")
def google_login(send: bool = False):
    """Start connecting Gmail (read-only). With ?send=true it also asks for the permission to send email."""
    return {"url": google_auth.start_login(allow_send=send)}


@app.get("/auth/google/callback")
def google_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Google sends the user back here. We finish the login, then return them to the app."""
    back = config.FRONTEND_ORIGIN.rstrip("/") + "/"
    if error:  # for example access_denied: the user pressed Cancel
        return RedirectResponse(back + "?" + urlencode({"google": "denied"}))
    try:
        if not code or not state:
            raise GoogleError("Google did not send back a sign-in code. Please try connecting again.", 400, "bad_callback")
        _, wanted_send = google_auth.finish_login(code, state)
    except GoogleError as e:
        return RedirectResponse(back + "?" + urlencode({"google": "error", "reason": str(e)}))
    gmail.clear_cache()
    activity.record("send_permission_granted" if wanted_send else "gmail_connected", account=google_auth.status()["email"])
    return RedirectResponse(back + "?" + urlencode({"google": "send_enabled" if wanted_send else "connected"}))


@app.post("/auth/google/disconnect")
def google_disconnect():
    """Forget the Google account (and revoke the permission at Google)."""
    who = google_auth.status()["email"]
    revoked = google_auth.disconnect()
    gmail.clear_cache()
    activity.record("gmail_disconnected", account=who)
    return {"disconnected": True, "revoked_at_google": revoked}


@app.get("/emails", response_model=list[Email], response_model_by_alias=True, response_model_exclude={"__all__": {"expected"}})
def list_emails(source: Literal["sample", "gmail"] = "sample", limit: int = Query(20, ge=1, le=gmail.MAX_LIMIT)):
    """Sample emails by default. source=gmail returns the newest real inbox emails (needs a connection)."""
    if source == "gmail":
        return gmail.list_inbox(limit)
    return load_emails()


@app.get("/emails/{email_id}", response_model=Email, response_model_by_alias=True, response_model_exclude={"expected"})
def read_email(email_id: str):
    email = get_email(email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return email
