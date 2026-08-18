"""
CLI Entry Point — Bitrix24 conversational agent (App5).
Alternative to the web UI (app.py). Interactive command-line loop.
"""

from services.agent import TaskAgent



def main():


    agent = TaskAgent()

    # Test connection
    try:
        user = agent.client.get_current_user()
        print(f" Connected to Bitrix24 as {user['name']} {user['last_name']} (ID: {user['id']})\n")
    except Exception as e:
        print(f" Unable to connect to Bitrix24: {e}")
        print("   Check your BITRIX24_WEBHOOK_URL in .env\n")
        return

    thread_id = "cli-session"

    while True:
        try:
            user_input = input("🗣️  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "quitter", "q"):
            print(" Goodbye!")
            break

        if user_input.lower() in ("new", "nouveau", "reset"):
            import uuid
            thread_id = str(uuid.uuid4())
            print(" New conversation started.\n")
            continue

        response = agent.handle(user_input, thread_id=thread_id)
        print(f"\n🤖 Agent: {response}\n")


if __name__ == "__main__":
    main()
