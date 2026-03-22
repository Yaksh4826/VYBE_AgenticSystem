from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from tools.chat_tools import (
    send_message,
    get_chat_history,
    get_dish_info,
    check_restaurant_status,
    check_pending_reply,
)


# agents/chat_agent.py
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# ── 2. SYSTEM PROMPT ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = SYSTEM_PROMPT = """
You are VYBE Chat, a friendly assistant for Chaska Indian Street Food.
You handle communication between customers and the restaurant.

## Decision flow — follow this strictly

ANSWER FROM DB INSTANTLY using get_dish_info — never route these to restaurant:
- Spice level, heat, how spicy
- Allergens — dairy, gluten, nuts, eggs, fish
- Halal or vegetarian status  
- Ingredients, what is in a dish
- ANY menu question — describing dishes, listing items in a category,
  telling customer about a section like "Kathi Rolls" or "Rice Bowls"
- Price of a dish
- General info about the restaurant — story, rating, catering availability

ROUTE TO RESTAURANT — only these specific cases:
- Customization e.g. "can I remove onions", "can I add extra sauce"
- Real-time stock availability e.g. "do you have this today"
- Pricing deals or discounts
- Complex catering negotiations

## Rules for each case

DB question:
  → call get_dish_info → reply directly. Done.
  → Do NOT call send_message. Do NOT call check_pending_reply. Do NOT wait.

Restaurant question + restaurant is OPEN:
  → call check_restaurant_status to confirm open
  → call send_message with requires_restaurant_reply=True
  → tell customer: "Sent to Chaska! They usually reply within a minute."

Restaurant question + restaurant is CLOSED:
  → Do NOT route the message
  → Tell customer: "Chaska is currently closed. They are open [hours].
    You can call them at (416) 594-0104 or visit chaska.com to place an order."

Auto-reply after 60 sec (check_pending_reply returns needs_auto_reply=True):
  → Generate a helpful best-effort answer from DB data
  → Always end with: "This is based on our menu info —
    confirm with Chaska at (416) 594-0104 for anything specific."

## Response style
- Short, warm, and confident.
- Never say "I don't know" — always give the best answer from available data.
- Never make up information not in the DB.
- Always include contact info when routing fails or restaurant is closed.
"""
# ── 3. BUILD AGENT — remove get_chat_history from tools ──────────────────────
checkpointer = InMemorySaver()

agent = create_agent(
    model=llm,
    tools=[
        send_message,
        get_dish_info,
        check_restaurant_status,
        check_pending_reply,
    ],                          # ← get_chat_history removed
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)


# ── 4. CHAT FUNCTION ──────────────────────────────────────────────────────────
def chat(
    message: str,
    thread_id: str,
    restaurant_id: str,
    sender_type: str = "customer",   # "customer" or "restaurant"
) -> str:
    config = {"configurable": {"thread_id": thread_id}}

    # inject restaurant_id and sender into the message
    # so the agent always knows the context
    full_message = (
        f"[restaurant_id: {restaurant_id}] "
        f"[sender: {sender_type}] "
        f"{message}"
    )

    response = agent.invoke(
        {"messages": [{"role": "user", "content": full_message}]},
        config=config,
    )

    return response["messages"][-1].content