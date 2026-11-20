import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

MIME_TYPES = {
    ".mp3": "audio/mp3",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".mp4": "video/mp4",
}


# Audio is sent inside the request, so keep files small (short meetings only)
MAX_BYTES = 18 * 1024 * 1024  # 18 MB

TRANSCRIBE_PROMPT = (
    "Transcribe this meeting recording word for word. "
    "Write in the same language that is spoken. "
    "If you can tell speakers apart, label them as Speaker 1, Speaker 2, etc. "
    "Return only the transcript text, nothing else."
)


def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in MIME_TYPES:
        raise ValueError(f"Unsupported audio type '{ext}'. Use: {', '.join(MIME_TYPES)}")
    if len(audio_bytes) > MAX_BYTES:
        raise ValueError("Audio file is too large. Please use a recording under 18 MB (about 10 minutes).")

    audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=MIME_TYPES[ext])

    last_error = None
    for attempt in range(5):  # up to 5 attempts
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=[TRANSCRIBE_PROMPT, audio_part],
            )
            text = (response.text or "").strip()
            if not text:
                raise ValueError("No speech could be transcribed from this audio.")
            return text

        except Exception as e:
            last_error = e
            msg = str(e)
            # Retry only when the service is busy or the rate limit is hit
            if "503" in msg or "429" in msg or "UNAVAILABLE" in msg:
                wait = 5 * (attempt + 1)
                print(f"Service busy, retrying in {wait} seconds ({attempt + 1}/5)...")
                time.sleep(wait)
            else:
                raise

    raise last_error