def draft_follow_up(recipient: str, topic: str) -> str:
    recipient = recipient.strip()
    topic = topic.strip()

    if not recipient:
        raise ValueError("Who should the message be addressed to?")
    if not topic:
        raise ValueError("What should the message be about?")

    return (
        f"Hi {recipient},\n\n"
        f"I'm following up about {topic}. "
        "Could you share an update when you have a chance?\n\n"
        "Thanks!"
    )