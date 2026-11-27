from datetime import datetime


def prepare_task(title: str, due_date: str) -> dict[str, str]:
    title = title.strip()
    due_date = due_date.strip()

    if not title:
        raise ValueError("Please provide a task title.")
    if not due_date:
        raise ValueError("When should this task be due?")

    return {"title": title, "due_date": due_date}


def task_create_payload(draft: dict[str, str]) -> dict[str, str]:
    title = draft["title"]
    if len(title) > 200:
        raise ValueError("Please shorten the task title to 200 characters or fewer.")

    date_prompt = (
        "What date, time, and timezone should I use? "
        "For example, use 2026-12-04T17:00:00+05:00."
    )
    try:
        due_date = datetime.fromisoformat(draft["due_date"])
    except ValueError:
        raise ValueError(date_prompt) from None
    if due_date.utcoffset() is None:
        raise ValueError(date_prompt)

    return {"title": title, "due_date": due_date.isoformat(), "source": "ai_agent"}
