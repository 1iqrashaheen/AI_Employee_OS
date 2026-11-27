from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Priority(str, Enum):
    high = "High"
    medium = "Medium"
    low = "Low"


class Status(str, Enum):
    unread = "unread"
    read = "read"
    draft = "draft"
    approved = "approved"
    sent = "sent"


class Expected(BaseModel):
    """Hand-labelled answers used to test the AI on Day 9. The AI never sees these."""

    priority: Priority
    category: str
    note: Optional[str] = None


class Tone(str, Enum):
    professional = "professional"
    friendly = "friendly"
    formal = "formal"
    firm = "firm"
    apologetic = "apologetic"
    concise = "concise"


class DraftRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=2000)
    tone: Tone = Tone.professional
    recipient: Optional[str] = Field(default=None, max_length=320)
    reply_to_email_id: Optional[str] = None


class DraftResponse(BaseModel):
    subject: str
    body: str
    recipient: Optional[str] = None
    status: str = "draft"
    notes: list[str] = []


CATEGORIES = [
    "support", "meeting", "invoice", "sales", "complaint", "contract", "project", "academic",
    "career", "internal", "notification", "newsletter", "marketing", "personal", "event",
    "security", "spam", "unclear", "other",
]


class AnalyzeRequest(BaseModel):
    """Analyze a stored email by id, or raw text pasted in."""

    email_id: Optional[str] = None
    subject: str = Field(default="", max_length=1000)
    body: str = Field(default="", max_length=200_000)
    sender: str = Field(default="", max_length=500)


class SummaryResult(BaseModel):
    summary: str
    action_items: list[str] = []
    truncated: bool = False


class ClassifyResult(BaseModel):
    priority: Priority
    category: str
    reason: str
    suspicious: bool = False
    truncated: bool = False


class DraftStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    sent = "sent"


class DraftContent(BaseModel):
    subject: str = Field(min_length=1, max_length=998)
    body: str = Field(min_length=1, max_length=100_000)
    recipient: Optional[str] = Field(default=None, max_length=320)


class DraftCreate(DraftContent):
    reply_to_email_id: Optional[str] = None
    instruction: Optional[str] = Field(default=None, max_length=2000)


class HistoryEvent(BaseModel):
    at: str
    event: str


class DraftRecord(BaseModel):
    id: str
    subject: str
    body: str
    recipient: Optional[str] = None
    reply_to_email_id: Optional[str] = None
    instruction: Optional[str] = None
    status: DraftStatus = DraftStatus.draft
    created_at: str
    updated_at: str
    approved_at: Optional[str] = None
    approved_hash: Optional[str] = None  # fingerprint of the exact content that was approved
    sent_at: Optional[str] = None
    delivery: Optional[str] = None  # "mock" (demo, nothing delivered) or "gmail" (really sent)
    delivery_id: Optional[str] = None  # Gmail's id for the sent message
    history: list[HistoryEvent] = []


class Email(BaseModel):
    id: str
    thread_id: str
    sender: str = Field(alias="from")
    subject: str
    body: str
    date: datetime
    summary: Optional[str] = None  # filled by AI (Day 4)
    priority: Optional[Priority] = None  # filled by AI (Day 4)
    status: Status = Status.unread
    expected: Optional[Expected] = None

    model_config = {"populate_by_name": True}
