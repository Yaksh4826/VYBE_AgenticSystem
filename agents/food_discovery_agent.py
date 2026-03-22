from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import InMemorySaver          # ← correct

from tools.search_food import search_food
from tools.get_nearby import get_nearby_restaurants
from db.supabase_client import supabase


# ── 1. LLM ────────────────────────────────────────────────────────────────────
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)


# ── 2. SYSTEM PROMPT ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are VYBE, a friendly and concise food discovery assistant.

You help users find food based on cravings, diet, budget, calories, 
protein, group size, or location.

## How to use your tools
- Always call search_food for any food or dish related query.
- For vegan requests use is_vegan=true
- For vegetarian requests use is_vegetarian=true
- For halal requests use is_halal=true
- For gluten-free use exclude_allergen="gluten"
- For nut-free use exclude_allergen="nuts"
- Call get_nearby_restaurants when the user mentions location or "near me".
- If the user refines a previous request remember the earlier context.

## How to respond
- Keep responses short and friendly.
- Format each result as: Dish name · Restaurant · Price · Calories
- If no results found, suggest the user broaden their search.
- Never make up dishes or restaurants.
- If the user asks to compare, sort, or pick from ALREADY shown results
  (e.g. "which has least calories", "which is cheapest"), DO NOT call
  search_food again. Just reason over the previous results directly.
- For group/catering items, note that calories shown are for the full bundle,
  not per person. Add "(total for bundle)" after calories for group items.

---

## User location
Default coordinates if not provided: lat=43.8971, lng=-78.8658
"""


# ── 3. MEMORY ─────────────────────────────────────────────────────────────────
# InMemorySaver handles short-term memory per thread_id automatically.
# We still save to Supabase separately for persistence across restarts.

checkpointer = InMemorySaver()


# ── 4. BUILD AGENT ────────────────────────────────────────────────────────────
agent = create_agent(
    model=llm,
    tools=[search_food, get_nearby_restaurants],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)


# ── 5. LOAD HISTORY FROM SUPABASE ─────────────────────────────────────────────
# On app restart, InMemorySaver is empty.
# This loads past messages from Supabase back into the checkpointer
# so the agent remembers conversations even after a restart.

def load_history(thread_id: str) -> list:
    response = (
        supabase
        .from_("chat_messages")
        .select("role, content")
        .eq("thread_id", thread_id)
        .order("created_at", desc=False)
        .limit(10)
        .execute()
    )

    messages = []
    for row in response.data:
        if row["role"] == "user":
            messages.append(HumanMessage(content=row["content"]))
        elif row["role"] == "assistant":
            messages.append(AIMessage(content=row["content"]))
    return messages


# ── 6. SAVE MESSAGE TO SUPABASE ───────────────────────────────────────────────
def save_message(thread_id: str, role: str, content: str):
    supabase.from_("chat_messages").insert({
        "thread_id": thread_id,
        "role": role,
        "content": content,
    }).execute()


# ── 7. CHAT FUNCTION ──────────────────────────────────────────────────────────
def chat(user_message: str, thread_id: str = "default") -> str:
    config = {"configurable": {"thread_id": thread_id}}

    response = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
    )

    reply = response["messages"][-1].content

    save_message(thread_id, "user", user_message)
    save_message(thread_id, "assistant", reply)

    return reply