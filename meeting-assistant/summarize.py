import os
import time
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


# Fixed output format (other modules will depend on this structure)
class ActionItem(BaseModel):
    task: str
    owner: Optional[str] = None
    deadline: Optional[str] = None  # YYYY-MM-DD or None


class MeetingResult(BaseModel):
    summary: str
    key_decisions: list[str]
    action_items: list[ActionItem]


PROMPT = """You are a meeting assistant.
Below is a meeting transcript. The meeting date is {date} ({weekday}).

Do the following:
1. Write a short summary (3-5 sentences).
2. List the key decisions that were made.
3. List all action items: task, owner (person's name), deadline.

Rules:
- Convert relative deadlines like "by Friday" or "next week" into a real date
  (YYYY-MM-DD) using the meeting date above.
- If the owner or deadline is not mentioned, use null.
- Do NOT invent anything that is not in the transcript.
- Write in the same language as the transcript.

Transcript:
{transcript}
"""


def summarize_transcript(transcript: str, meeting_date: str, weekday: str) -> MeetingResult:
    prompt = PROMPT.format(date=meeting_date, weekday=weekday, transcript=transcript)

    last_error = None
    for attempt in range(5):  # up to 5 attempts
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=MeetingResult,
                    temperature=0.2,
                ),
            )
            return MeetingResult.model_validate_json(response.text)

        except Exception as e:
            last_error = e
            msg = str(e)
            # Retry only when the service is busy or the rate limit is hit
            if "503" in msg or "429" in msg or "UNAVAILABLE" in msg:
                wait = 5 * (attempt + 1)
                print(f"Service busy, retrying in {wait} seconds ({attempt + 1}/5)...")
                time.sleep(wait)
            else:
                raise  # any other error is shown immediately

    raise last_error