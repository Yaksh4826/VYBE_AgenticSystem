from dotenv import load_dotenv
load_dotenv()

import json
import re
from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from tools.chat_tools import (
    send_message,
    get_dish_info,
    check_restaurant_status,
    check_pending_reply,
)


# agents/chat_agent.py
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# ── 2. SYSTEM PROMPTS ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are VYBE Chat, an assistant for Chaska Indian Street Food.

You only handle DB-answerable menu questions.
Always call get_dish_info first, then answer clearly using only that tool output.
If no matching dish info is found, say that you could not find an exact match and
ask a short clarifying question.
Keep replies concise and friendly.
"""

AUTO_REPLY_PROMPT = """
You are VYBE Chat fallback assistant.

The restaurant has not replied in time. Use get_dish_info with best-effort matching
from the user's query and provide the most likely helpful answer from menu data only.
Do not hallucinate.
Keep it concise.
"""

# ── 3. BUILD AGENTS ────────────────────────────────────────────────────────────
checkpointer = InMemorySaver()

db_agent = create_agent(
    model=llm,
    tools=[
        get_dish_info,
    ],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

auto_reply_agent = create_agent(
    model=llm,
    tools=[get_dish_info],
    system_prompt=AUTO_REPLY_PROMPT,
    checkpointer=checkpointer,
)


RESTAURANT_REQUIRED_PATTERNS = [
    r"\bremove\b",
    r"\bwithout\b",
    r"\bno onions?\b",
    r"\bextra\b",
    r"\badd\b",
    r"\bcustom(?:ize|ization)?\b",
    r"\bavailable\b",
    r"\bin stock\b",
    r"\btoday\b",
    r"\bopen\b",
    r"\bclosed\b",
    r"\blate night\b",
    r"\bcatering\b",
    r"\bdiscount\b",
    r"\bdeal\b",
]


def _needs_restaurant_assistance(message: str) -> bool:
    text = message.lower()
    return any(re.search(pattern, text) for pattern in RESTAURANT_REQUIRED_PATTERNS)


def _parse_json_or_default(raw: str, default: dict) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        return default


# ── 4. CHAT FUNCTION ──────────────────────────────────────────────────────────
def chat(
    message: str,
    thread_id: str,
    restaurant_id: str,
    sender_type: str = "customer",   # "customer" or "restaurant"
) -> str:
    config = {"configurable": {"thread_id": thread_id}}

    # Restaurant-side messages are logged directly.
    if sender_type == "restaurant":
        send_message.invoke({
            "thread_id": thread_id,
            "restaurant_id": restaurant_id,
            "sender_type": "restaurant",
            "content": message,
            "requires_restaurant_reply": False,
        })
        return "Restaurant message logged."

    # Always check pending unanswered restaurant messages first.
    pending_raw = check_pending_reply.invoke({
        "thread_id": thread_id,
        "restaurant_id": restaurant_id,
    })
    pending = _parse_json_or_default(pending_raw, {"needs_auto_reply": False})
    if pending.get("needs_auto_reply"):
        full_message = (
            f"[restaurant_id: {restaurant_id}] "
            f"[sender: {sender_type}] "
            f"{message}"
        )
        response = auto_reply_agent.invoke(
            {"messages": [{"role": "user", "content": full_message}]},
            config=config,
        )
        fallback = response["messages"][-1].content
        return (
            "I haven't heard back from Chaska yet, but here's what I found:\n"
            f"{fallback}\n\n"
            "This is based on our menu info - confirm with Chaska at (416) 594-0104."
        )

    # Route restaurant-required questions with status check first.
    if _needs_restaurant_assistance(message):
        status_raw = check_restaurant_status.invoke({"restaurant_id": restaurant_id})
        status = _parse_json_or_default(status_raw, {})
        if status.get("status") == "CLOSED":
            opening = status.get("opening_time", "N/A")
            closing = status.get("closing_time", "N/A")
            return (
                "I haven't heard back from Chaska yet - they are currently closed.\n"
                f"They are open from {opening} to {closing}.\n"
                "You can call them at (416) 594-0104."
            )

        send_message.invoke({
            "thread_id": thread_id,
            "restaurant_id": restaurant_id,
            "sender_type": "customer",
            "content": message,
            "requires_restaurant_reply": True,
        })
        return "Sent to Chaska! They usually reply within a minute."

    # DB-answerable path: respond immediately from menu data.
    full_message = (
        f"[restaurant_id: {restaurant_id}] "
        f"[sender: {sender_type}] "
        f"{message}"
    )

    response = db_agent.invoke(
        {"messages": [{"role": "user", "content": full_message}]},
        config=config,
    )

    return response["messages"][-1].content