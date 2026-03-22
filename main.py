from dotenv import load_dotenv
load_dotenv()

from agents.food_discovery_agent import chat


def run_conversation(thread_id: str, messages: list[str]):
    print(f"\n{'=' * 50}")
    print(f"SESSION: {thread_id}")
    print('=' * 50)

    for message in messages:
        print(f"\nYou : {message}")
        response = chat(message, thread_id=thread_id)
        print(f"VYBE: {response}")
        print("-" * 40)


if __name__ == "__main__":

    # ── TEST 1: Basic food queries ─────────────────────────────────────────
    run_conversation(
        thread_id="user_001",
        messages=[
            "I'm craving something cheesy",
            "Make it under $15",              # agent should remember cheesy
            "Which one has the least calories?",  # agent should remember both
        ]
    )

    # ── TEST 2: Diet + budget ──────────────────────────────────────────────
    run_conversation(
        thread_id="user_002",
        messages=[
            "Show me vegan food under 500 calories",
            "Any of those under $12?",        # agent should remember vegan
        ]
    )

    # ── TEST 3: High protein near me ──────────────────────────────────────
    run_conversation(
        thread_id="user_003",
        messages=[
            "What high protein meals are near me?",
            "Show me only the ones under $20",
        ]
    )

    # ── TEST 4: Group order ────────────────────────────────────────────────
    run_conversation(
        thread_id="user_004",
        messages=[
            "I need food for a party of 20 people",
        ]
    )