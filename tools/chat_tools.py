import json
from datetime import datetime, timezone
from langchain_core.tools import tool
from pydantic import BaseModel
from typing import Optional
from db.supabase_client import supabase


# ── SCHEMAS ───────────────────────────────────────────────────────────────────

class SendMessageInput(BaseModel):
    thread_id: str
    restaurant_id: str
    sender_type: str
    content: str
    requires_restaurant_reply: Optional[bool] = False

class GetChatHistoryInput(BaseModel):
    thread_id: str
    limit: Optional[int] = 10

class GetDishInfoInput(BaseModel):
    dish_name: str
    restaurant_id: Optional[str] = None

class CheckRestaurantStatusInput(BaseModel):
    restaurant_id: str

class CheckPendingReplyInput(BaseModel):
    thread_id: str
    restaurant_id: str


# ── TOOL 1: SEND MESSAGE ──────────────────────────────────────────────────────

@tool(args_schema=SendMessageInput)
def send_message(
    thread_id: str,
    restaurant_id: str,
    sender_type: str,
    content: str,
    requires_restaurant_reply: Optional[bool] = False,
) -> str:
    """
    Send or log a message in a chat thread.
    Only call this for customer→restaurant routing.
    Do NOT call this for instant DB replies — just reply directly.
    """
    supabase.from_("chat_messages").insert({
        "thread_id": thread_id,
        "restaurant_id": restaurant_id,
        "role": sender_type,
        "content": content,
        "requires_restaurant_reply": requires_restaurant_reply,
        "is_auto_reply": sender_type == "ai",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    return f"Message logged."

# ── TOOL 2: GET CHAT HISTORY ──────────────────────────────────────────────────

@tool(args_schema=GetChatHistoryInput)
def get_chat_history(
    thread_id: str,
    limit: Optional[int] = 10,
) -> str:
    """
    Load full chat history for a thread so the agent has context.
    Always call this at the start of a new conversation.
    """
    response = (
        supabase
        .from_("chat_messages")
        .select("role, content, created_at, is_auto_reply")
        .eq("thread_id", thread_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )

    if not response.data:
        return "No messages yet in this conversation."

    formatted = []
    for msg in response.data:
        tag = " [AUTO]" if msg.get("is_auto_reply") else ""
        formatted.append(f"[{msg['role'].upper()}{tag}]: {msg['content']}")

    return "\n".join(formatted)


# ── TOOL 3: GET DISH INFO ─────────────────────────────────────────────────────

@tool(args_schema=GetDishInfoInput)
def get_dish_info(
    dish_name: str,
    restaurant_id: Optional[str] = None,
) -> str:
    """
    Get detailed info about a dish — spice level, allergens, ingredients,
    halal status, vegetarian status. Use this to instantly answer customer
    questions that can be resolved from menu data without asking the restaurant.
    Examples: "is this spicy", "does this have nuts", "is this halal"
    """
    q = (
        supabase
        .from_("food_dishes")
        .select("""
            name, spicy_level, allergens, ingredients,
            calories, proteins_g, price,
            is_halal, is_vegetarian, description,
            restaurants ( name )
        """)
        .ilike("name", f"%{dish_name}%")
    )

    if restaurant_id:
        q = q.eq("restaurant_id", restaurant_id)

    response = q.limit(3).execute()

    if not response.data:
        return f"No dish found matching '{dish_name}'. Ask the restaurant directly."

    results = []
    for dish in response.data:
        spice_labels = ["none", "mild", "medium", "hot", "very hot", "extreme"]
        spice = spice_labels[min(dish.get("spicy_level", 0), 5)]

        results.append({
            "dish": dish["name"],
            "restaurant": dish["restaurants"]["name"] if dish.get("restaurants") else "Unknown",
            "spicy_level": spice,
            "allergens": dish.get("allergens", []),
            "ingredients": dish.get("ingredients", []),
            "is_halal": dish.get("is_halal", False),
            "is_vegetarian": dish.get("is_vegetarian", False),
            "description": dish.get("description", ""),
            "calories": dish.get("calories", "N/A"),
            "price": f"${dish['price']}",
        })

    return json.dumps(results, indent=2)


# ── TOOL 4: CHECK RESTAURANT STATUS ──────────────────────────────────────────

@tool(args_schema=CheckRestaurantStatusInput)
def check_restaurant_status(restaurant_id: str) -> str:
    """
    Check if a restaurant is currently open or closed.
    Use this before routing a message to the restaurant.
    If closed, auto-reply immediately instead of waiting.
    """
    response = (
        supabase
        .from_("restaurants")
        .select("name, opening_time, closing_time")
        .eq("id", restaurant_id)
        .single()
        .execute()
    )

    if not response.data:
        return "Restaurant not found."

    r = response.data
    now = datetime.now().strftime("%H:%M:%S")
    is_open = r["opening_time"] <= now <= r["closing_time"]

    return json.dumps({
        "name": r["name"],
        "status": "OPEN" if is_open else "CLOSED",
        "opening_time": r["opening_time"],
        "closing_time": r["closing_time"],
    })


# ── TOOL 5: CHECK PENDING REPLY ───────────────────────────────────────────────
# This is the 60 second threshold check.
# Called after sending a message that requires restaurant reply.
# If 60 seconds passed with no restaurant response, returns needs_auto_reply=True.

@tool(args_schema=CheckPendingReplyInput)
def check_pending_reply(thread_id: str, restaurant_id: str) -> str:
    """
    Check if the restaurant has replied to the last customer message.
    If more than 60 seconds have passed with no reply, returns
    needs_auto_reply=True so the agent generates a best-effort answer.
    """
    # get last customer message that requires restaurant reply
    last_msg = (
        supabase
        .from_("chat_messages")
        .select("created_at, requires_restaurant_reply")
        .eq("thread_id", thread_id)
        .eq("restaurant_id", restaurant_id)
        .eq("requires_restaurant_reply", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not last_msg.data:
        return json.dumps({"needs_auto_reply": False})

    # check if restaurant replied after that message
    last_customer_time = last_msg.data[0]["created_at"]

    restaurant_reply = (
        supabase
        .from_("chat_messages")
        .select("created_at")
        .eq("thread_id", thread_id)
        .eq("restaurant_id", restaurant_id)
        .eq("role", "restaurant")
        .gte("created_at", last_customer_time)
        .limit(1)
        .execute()
    )

    if restaurant_reply.data:
        return json.dumps({"needs_auto_reply": False, "reason": "restaurant replied"})

    # check how long ago the customer message was sent
    sent_at = datetime.fromisoformat(last_customer_time.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    seconds_elapsed = (now - sent_at).total_seconds()

    if seconds_elapsed >= 60:
        return json.dumps({
            "needs_auto_reply": True,
            "seconds_elapsed": round(seconds_elapsed),
            "reason": "restaurant did not reply within 60 seconds"
        })

    return json.dumps({
        "needs_auto_reply": False,
        "seconds_elapsed": round(seconds_elapsed),
        "reason": "still within 60 second window"
    })