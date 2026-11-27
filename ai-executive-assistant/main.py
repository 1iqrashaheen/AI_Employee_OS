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


from assistant import ask_gemini, create_gemini_client


def main() -> None:
    history: list[tuple[str, str]] = []
    print("Enter a request, or type 'history' or 'exit'.")

    with create_gemini_client() as client:
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
            reply = ask_gemini(client, history)
            print(reply)
            history.append(("Assistant", reply))


if __name__ == "__main__":
    main()