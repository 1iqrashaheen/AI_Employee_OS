# from tools.task_tools import prepare_task


# def main() -> None:
#     history: list[tuple[str, str]] = []
#     print("Enter a task, or type 'history' or 'exit'.")

#     while True:
#         instruction = input("What task should I prepare? ").strip()

#         if instruction.lower() == "exit":
#             return
#         if instruction.lower() == "history":
#             for speaker, message in history:
#                 print(f"{speaker}: {message}")
#             continue

#         history.append(("You", instruction))
#         title, _, due_date = instruction.partition(" by ")

#         if title.strip() and not due_date.strip():
#             question = "When should this task be due?"
#             history.append(("Assistant", question))
#             due_date = input(f"{question} ")
#             history.append(("You", due_date))

#         try:
#             draft = prepare_task(title, due_date)
#             reply = f"Task draft: {draft['title']} (due {draft['due_date']})"
#         except ValueError as error:
#             reply = str(error)

#         print(reply)
#         history.append(("Assistant", reply))


# if __name__ == "__main__":
#     main()


import argparse
import os
from getpass import getpass

from assistant import create_gemini_client, get_assistant_reply
from providers.api_provider import TaskManager, TaskManagerError
from tools.task_tools import task_create_payload


def main(*, prompt_task_token: bool = False) -> None:
    history: list[tuple[str, str]] = []
    pending_task: dict[str, str] | None = None
    with create_gemini_client() as client:
        api_url = os.getenv("TASK_MANAGER_API_URL", "").strip()
        token = os.getenv("TASK_MANAGER_TOKEN", "").strip()
        if prompt_task_token:
            if not api_url:
                raise SystemExit("Set TASK_MANAGER_API_URL before signing in to Task Manager.")
            token = getpass("Paste Swagger's data.access_token, then press Return: ").strip()
            if not token:
                raise SystemExit("No access token was pasted. Restart and paste data.access_token.")
        try:
            task_manager = TaskManager(api_url, token) if api_url else None
        except ValueError as error:
            raise SystemExit(f"Task Manager configuration error: {error}") from error
        if prompt_task_token and task_manager is not None:
            try:
                workspace = task_manager.authorized_workspace()
            except TaskManagerError as error:
                raise SystemExit(str(error)) from error
            print(f"Signed in to Task Manager workspace: {workspace}")

        print("Enter a request, or type 'history' or 'exit'.")
        while True:
            instruction = input("What would you like me to do? ").strip()
            command = instruction.lower()

            if command == "exit":
                return
            if command == "history":
                for speaker, message in history:
                    print(f"{speaker}: {message}")
                continue
            if not instruction:
                continue

            history.append(("You", instruction))
            if command == "approve":
                if pending_task is None or task_manager is None:
                    reply = "There is no task draft ready to approve."
                else:
                    approved_task = pending_task
                    pending_task = None
                    try:
                        task_id = task_manager.create_task(approved_task)
                    except TaskManagerError as error:
                        reply = str(error)
                    else:
                        reply = f"Task created: {approved_task['title']} (ID: {task_id})"
            elif command == "cancel":
                reply = "Task draft cancelled." if pending_task else "There is no task to cancel."
                pending_task = None
            else:
                pending_task = None
                result = get_assistant_reply(client, history)
                reply = result.text
                if task_manager is not None and len(result.task_drafts) == 1:
                    try:
                        pending_task = task_create_payload(result.task_drafts[0])
                    except ValueError as error:
                        reply += f"\n{error}"
                    else:
                        reply += "\nType 'approve' to create this task or 'cancel' to discard it."
                elif task_manager is not None and result.task_drafts:
                    reply += "\nPlease prepare one task at a time for approval."
            print(reply)
            history.append(("Assistant", reply))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Executive Assistant")
    parser.add_argument(
        "--prompt-task-token",
        action="store_true",
        help="Prompt for the hosted Task Manager access token and verify the workspace.",
    )
    main(prompt_task_token=parser.parse_args().prompt_task_token)
