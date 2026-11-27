def prepare_task(title: str, due_date: str) -> dict[str, str]:
    title = title.strip()
    due_date = due_date.strip()

    if not title:
        raise ValueError("Please provide a task title.")
    if not due_date:
        raise ValueError("When should this task be due?")

    return {"title": title, "due_date": due_date}