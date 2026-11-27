import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # project-root .env, if present

DATA_FILE = Path(
    os.getenv("EMAIL_DATA_FILE", Path(__file__).resolve().parents[2] / "data" / "sample_emails.json")
)

# LLM provider is chosen on Day 3: "claude", "openai" or "gemini"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")  # optional override; sensible default per provider

# Real email connection (Day 7). Empty means sample-emails mode.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

# Saved drafts and their approval state (a small JSON file; replaced by a database later if needed).
DRAFTS_FILE = Path(os.getenv("DRAFTS_FILE", Path(__file__).resolve().parents[2] / "data" / "drafts.json"))

# Append-only record of approvals and sends (no email bodies). One JSON object per line.
ACTIVITY_FILE = Path(os.getenv("ACTIVITY_FILE", Path(__file__).resolve().parents[2] / "data" / "activity.jsonl"))

# Where the Google login result (access and refresh tokens) is kept. Gitignored. Never returned by the API.
GOOGLE_TOKEN_FILE = Path(
    os.getenv("GOOGLE_TOKEN_FILE", Path(__file__).resolve().parents[2] / "data" / "google.token.json")
)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
