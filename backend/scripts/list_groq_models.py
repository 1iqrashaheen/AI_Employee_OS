"""Print the model IDs your Groq key can use right now. Pick one and set LLM_MODEL in .env.

Usage (from backend/):  LLM_PROVIDER=groq python scripts/list_groq_models.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config, llm  # noqa: E402

if not config.LLM_API_KEY:
    sys.exit("Set LLM_API_KEY (your Groq key) in .env first.")
for model_id in llm.list_groq_models():
    print(model_id)
