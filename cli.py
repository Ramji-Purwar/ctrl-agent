from core.agent_loop import run_agent
from core.memory import clear_history
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

print("AI Agent CLI — type 'quit' to exit, 'clear' to reset history\n")

while True:
    try:
        user_input = input("You: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        break

    if not user_input:
        continue
    if user_input.lower() == "quit":
        break
    if user_input.lower() == "clear":
        clear_history()
        print("History cleared.\n")
        continue

    result = run_agent(user_input)
    print(f"\nAgent: {result['response']}")

    if result.get("tools_used"):
        print(f"[Tools used: {', '.join(result['tools_used'])}]")
    print()