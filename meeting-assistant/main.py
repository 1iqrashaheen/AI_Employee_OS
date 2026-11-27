from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from summarize import MeetingResult, summarize_transcript
from transcribe import transcribe_audio

app = FastAPI(title="Meeting Assistant API")


class SummarizeRequest(BaseModel):
    transcript: str
    meeting_date: Optional[str] = None  # YYYY-MM-DD, defaults to today


class AudioMeetingResult(BaseModel):
    transcript: str
    result: MeetingResult


def parse_date(meeting_date: Optional[str]) -> date:
    if not meeting_date:
        return date.today()
    try:
        return datetime.strptime(meeting_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="meeting_date must be in YYYY-MM-DD format.")


@app.get("/")
def health():
    return {"status": "ok", "module": "meeting-assistant"}


@app.post("/meetings/summarize", response_model=MeetingResult)
def summarize(req: SummarizeRequest):
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty.")

    d = parse_date(req.meeting_date)
    try:
        return summarize_transcript(
            req.transcript,
            meeting_date=d.isoformat(),
            weekday=d.strftime("%A"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")


@app.post("/meetings/summarize-audio", response_model=AudioMeetingResult)
async def summarize_audio(
    file: UploadFile = File(...),
    meeting_date: Optional[str] = Form(None),
):
    d = parse_date(meeting_date)
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio file is empty.")

    try:
        transcript = transcribe_audio(audio_bytes, file.filename or "audio.mp3")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Transcription error: {e}")

    try:
        result = summarize_transcript(
            transcript,
            meeting_date=d.isoformat(),
            weekday=d.strftime("%A"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return AudioMeetingResult(transcript=transcript, result=result)