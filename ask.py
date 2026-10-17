"""Try Ustad from the terminal: type a question, read the Urdu answer."""
from app.tutor import ask_ustad

print("Ustad is ready! Type a question (or 'exit' to stop).\n")

while True:
    question = input("Child: ").strip()
    if question.lower() in ("exit", "quit"):
        break
    if not question:
        continue  # ignore empty input

    try:
        result = ask_ustad(question)
    except Exception as error:
        # Show problems (like rate limits) without crashing the program
        print(f"Something went wrong: {error}\n")
        continue

    print(f"\n[Subject: {result['subject']} | Safe: {result['safe']}]")
    print("Ustad:", result["explanation_urdu"])
    if result["check_question_urdu"]:
        print("Question for you:", result["check_question_urdu"])
    print()