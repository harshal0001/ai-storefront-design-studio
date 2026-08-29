"""CLI entry point for interactive terminal sessions.

This provides a simple terminal-based interface for testing the agent.
For web UI development, use the FastAPI server (server.py).
For production deployment, use the AgentCore runtime (runtime.py).
"""

from .agent import create_agent
from .agent_memory import memory_persist_context
from .config import DEFAULT_SHOP_UUID, GREETING_PROMPT
from .tools import reset_all


def main():
    """Run the interactive storefront design session in terminal."""
    agent = create_agent(
        merchant_id=DEFAULT_SHOP_UUID,
        session_id=f"cli-{DEFAULT_SHOP_UUID}",
    )

    print("\n" + "=" * 60)
    print("  Storefront Design Studio")
    print("  Your friendly design companion")
    print("=" * 60)
    print("\nType 'quit' to exit, 'reset' to start over.\n")

    with memory_persist_context(enabled=False):
        greeting = agent(GREETING_PROMPT)
    print(f"Studio: {greeting}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nThanks for designing with me! Your storefront is going to look amazing.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("\nThanks for designing with me! Your storefront is going to look amazing.")
            break

        if user_input.lower() == "reset":
            reset_all()
            print("\nStarting fresh! Let's design something beautiful.\n")
            with memory_persist_context(enabled=False):
                greeting = agent(
                    "The merchant wants to start over. "
                    "Greet them fresh and ask about their vibe."
                )
            print(f"Studio: {greeting}\n")
            continue

        response = agent(user_input)
        print(f"\nStudio: {response}\n")


if __name__ == "__main__":
    main()
