from dotenv import load_dotenv
load_dotenv()

import time
from agents.chat_agent import chat as restaurant_chat

# ── Use Chaska's real UUID from your restaurants table ────────────────────────
# Run this in Supabase to get it:
# select id from restaurants where name = 'Chaska Indian Street Food';
CHASKA_ID = "b2c3d4e5-0001-0001-0001-000000000001"


def divider(label):
    print(f"\n{'=' * 50}")
    print(f" {label}")
    print('=' * 50)


def customer(msg, thread, delay=0):
    if delay:
        time.sleep(delay)
    print(f"\nCustomer : {msg}")
    reply = restaurant_chat(
        message=msg,
        thread_id=thread,
        restaurant_id=CHASKA_ID,
        sender_type="customer",
    )
    print(f"VYBE     : {reply}")
    print("-" * 40)


def restaurant(msg, thread):
    print(f"\nRestaurant: {msg}")
    restaurant_chat(
        message=msg,
        thread_id=thread,
        restaurant_id=CHASKA_ID,
        sender_type="restaurant",
    )
    print("  [message logged to DB]")
    print("-" * 40)


if __name__ == "__main__":

    # ── TEST 1: DB can answer instantly ───────────────────────────────────────
    # These should never go to restaurant — answered from food_dishes table
    divider("TEST 1 — Instant DB replies")

    customer("Is the Butter Chicken spicy?",          thread="chat_001")
    customer("Does the Tandoori Chicken have dairy?", thread="chat_002")
    customer("Is the Samosa Chaat vegetarian?",       thread="chat_003")
    customer("Is the Tandoori Chicken halal?",        thread="chat_004")

    # ── TEST 2: Memory within a thread ────────────────────────────────────────
    # Second message has no context on its own — agent must remember thread
    divider("TEST 2 — Memory within conversation")

    customer("Tell me about the Kathi Rolls",         thread="chat_005")
    customer("Are any of those vegan?",               thread="chat_005")  # no context alone
    customer("Which one is cheapest?",                thread="chat_005")  # no context alone

    # ── TEST 3: Must go to restaurant ─────────────────────────────────────────
    # Customization — DB cannot answer this
    divider("TEST 3 — Route to restaurant, restaurant replies fast")

    customer("Can I remove onions from my Kathi Roll?", thread="chat_006")
    time.sleep(2)   # simulate restaurant seeing the message
    restaurant("Yes absolutely, we can customize any roll for you!", thread="chat_006")
    customer("Great! Can I also add extra sauce?",       thread="chat_006")

    # ── TEST 4: Restaurant does not reply — 60 sec auto-reply triggers ────────
    # Agent routes to restaurant, waits 60 sec, then auto-replies from DB
    divider("TEST 4 — Restaurant silent, auto-reply after 60 sec")

    customer(
        "Do you offer catering for 30 people?",
        thread="chat_007",
    )
    print("\n  [Simulating restaurant not replying — waiting 62 seconds...]")
    time.sleep(62)  # wait past the 60 sec threshold

    # this second message triggers check_pending_reply
    # agent sees 60+ sec elapsed, generates best-effort answer
    customer(
        "Hello? Anyone there?",
        thread="chat_007",
    )

    # ── TEST 5: Restaurant closed ─────────────────────────────────────────────
    # Agent should detect restaurant is closed and not route message
    divider("TEST 5 — Restaurant closed")

    customer(
        "Can I place a late night order?",
        thread="chat_008",
    )