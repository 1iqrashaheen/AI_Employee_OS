# import os

# from google import genai
# from google.genai import types

# from tools.message_tools import draft_follow_up
# from tools.task_tools import prepare_task


# def main() -> None:
#     instruction = input("What would you like me to do? ")

#     config = types.GenerateContentConfig(
#         tools=[prepare_task, draft_follow_up],
#         automatic_function_calling=types.AutomaticFunctionCallingConfig(
#             disable=True
#         ),
#         system_instruction=(
#             "Use prepare_task for task drafts and draft_follow_up for follow-up "
#             "messages. Ask for any missing details. Do not invent dates, names, "
#             "or topics. Keep the date wording the user provided."
#         ),
#     )

#     with genai.Client(api_key=os.environ["GEMINI_API_KEY"]) as client:
#         response = client.models.generate_content(
#             model="gemini-3.5-flash-lite",
#             contents=instruction,
#             config=config,
#         )

#     if response.function_calls:
#         for call in response.function_calls:
#             print(f"Suggested function: {call.name}")
#             print(f"Details: {call.args}")
#     else:
#         print(response.text or "Gemini returned no suggestion.")


# if __name__ == "__main__":
#     main()

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from tools.message_tools import draft_follow_up
from tools.task_tools import prepare_task


@dataclass
class AssistantReply:
    text: str
    task_drafts: list[dict[str, str]] = field(default_factory=list)


def create_gemini_client() -> genai.Client:
    load_dotenv(Path(__file__).with_name(".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Add GEMINI_API_KEY to the .env file next to assistant.py.")
    return genai.Client(api_key=api_key)


def text_argument(arguments: dict, name: str) -> str:
    value = arguments.get(name, "")
    if not isinstance(value, str):
        raise ValueError(f"The {name.replace('_', ' ')} must be text.")
    return value


def run_suggested_function(call: types.FunctionCall) -> AssistantReply:
    arguments = call.args or {}

    if call.name == "prepare_task":
        task = prepare_task(
            title=text_argument(arguments, "title"),
            due_date=text_argument(arguments, "due_date"),
        )
        return AssistantReply(
            f"Task draft: {task['title']} (due {task['due_date']})", [task]
        )

    if call.name == "draft_follow_up":
        message = draft_follow_up(
            recipient=text_argument(arguments, "recipient"),
            topic=text_argument(arguments, "topic"),
        )
        return AssistantReply(message)

    raise ValueError("I can prepare task drafts and follow-up messages.")


def ask_gemini(client: genai.Client, history: list[tuple[str, str]]) -> str:
    return get_assistant_reply(client, history).text


def get_assistant_reply(
    client: genai.Client, history: list[tuple[str, str]]
) -> AssistantReply:
    conversation = [
        types.Content(
            role="user" if speaker == "You" else "model",
            parts=[types.Part(text=message)],
        )
        for speaker, message in history
    ]

    config = types.GenerateContentConfig(
        tools=[prepare_task, draft_follow_up],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        system_instruction=(
            "Use prepare_task for task drafts and draft_follow_up for follow-up "
            "messages. Use earlier messages to understand follow-ups and keep "
            "draft details the user hasn't changed. Ask for missing details. "
            "Do not invent dates, names, or topics. Keep date wording as provided. "
            "Task creation is handled by the app after approval. "
            "Use prepare_task for task creation requests and never claim a task was created."
        ),
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=conversation,
            config=config,
        )
    except errors.APIError as error:
        return AssistantReply(f"Gemini request failed (HTTP {error.code}). Please try again.")

    if not response.function_calls:
        return AssistantReply(response.text or "Gemini returned no suggestion.")

    replies = []
    task_drafts = []
    for call in response.function_calls:
        try:
            reply = run_suggested_function(call)
        except ValueError as error:
            replies.append(str(error))
        else:
            replies.append(reply.text)
            task_drafts.extend(reply.task_drafts)
    return AssistantReply("\n\n".join(replies), task_drafts)


def main() -> None:
    instruction = input("What would you like me to do? ").strip()
    if instruction:
        with create_gemini_client() as client:
            print(ask_gemini(client, [("You", instruction)]))


if __name__ == "__main__":
    main()
