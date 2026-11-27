"""Provider-agnostic LLM client. One function: complete_json(system, user) -> str.

Providers: claude | openai | gemini | mock. Plain HTTP (httpx), no vendor SDKs.
The mock provider needs no key and lets the whole app and test suite run offline.
"""
import httpx

from . import config

TIMEOUT = 60.0

DEFAULT_MODELS = {
    "claude": "claude-sonnet-5-5",
    "openai": "gpt-4o-mini",
    # llama-3.3-70b-versatile was retired by Groq on 2026-08-16; this is Groq's recommended production replacement.
    "groq": "openai/gpt-oss-120b",
    "gemini": "gemini-2.0-flash",
}


class LLMError(Exception):
    pass


def _model() -> str:
    return config.LLM_MODEL or DEFAULT_MODELS.get(config.LLM_PROVIDER, "")


def _claude(system: str, user: str) -> str:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": config.LLM_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": _model(),
            "max_tokens": 1024,
            "temperature": 0.4,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"])


def _openai_compatible(base_url: str, system: str, user: str) -> str:
    r = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        json={
            "model": _model(),
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"] or ""


def _openai(system: str, user: str) -> str:
    return _openai_compatible("https://api.openai.com/v1", system, user)


def _groq(system: str, user: str) -> str:
    # Groq exposes an OpenAI-compatible API.
    return _openai_compatible("https://api.groq.com/openai/v1", system, user)


def list_groq_models() -> list[str]:
    """Model IDs the configured Groq key can use right now."""
    r = httpx.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return sorted(m["id"] for m in r.json()["data"])


def _gemini(system: str, user: str) -> str:
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{_model()}:generateContent",
        headers={"x-goog-api-key": config.LLM_API_KEY},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _mock(system: str, user: str) -> str:
    """Deterministic fake model: echoes the instruction into a tidy draft. For tests and demos."""
    import json
    import re

    # Offline stand-in for the Day 4 analysis prompts: valid JSON in the right shape, no real judgment.
    if "<task>summarize</task>" in user:
        subj = re.search(r"Subject: (.*)", user)
        return json.dumps({"summary": f"[mock] Email about: {subj.group(1) if subj else 'unknown'}", "action_items": []})
    if "<task>classify</task>" in user:
        return json.dumps({"priority": "Medium", "category": "other", "reason": "[mock] no real analysis", "suspicious": False})

    m = re.search(r"<instruction>\n?(.*?)\n?</instruction>", user, re.S)
    instruction = (m.group(1) if m else user).strip().rstrip(".")
    return json.dumps(
        {
            "subject": instruction[:60].capitalize(),
            "body": f"Hello,\n\n{instruction}.\n\nBest regards",
        }
    )


PROVIDERS = {"claude": _claude, "openai": _openai, "groq": _groq, "gemini": _gemini, "mock": _mock}


KEYLESS = {"mock"}  # providers that need no API key (the evaluation kit adds its scripted ones while it runs)


def is_configured() -> bool:
    if config.LLM_PROVIDER in KEYLESS:
        return True
    return config.LLM_PROVIDER in PROVIDERS and bool(config.LLM_API_KEY)


def complete_json(system: str, user: str) -> str:
    if not is_configured():
        raise LLMError(
            "No LLM configured. Set LLM_PROVIDER (claude, openai, gemini or mock) and LLM_API_KEY in .env."
        )
    try:
        return PROVIDERS[config.LLM_PROVIDER](system, user)
    except httpx.HTTPStatusError as e:
        detail = ""
        try:  # providers put a readable reason in the error body, e.g. "model does not exist"
            err = e.response.json().get("error", {})
            detail = err.get("message", "") if isinstance(err, dict) else str(err)
        except ValueError:
            pass
        hint = " Check LLM_MODEL: the model may have been retired." if e.response.status_code == 404 else ""
        raise LLMError(
            f"{config.LLM_PROVIDER} returned HTTP {e.response.status_code}: {detail[:200]}.{hint}".replace("..", ".")
        ) from e
    except (httpx.HTTPError, KeyError, IndexError) as e:
        raise LLMError(f"LLM call failed: {type(e).__name__}") from e
