from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessage

from tools.search_food import search_food
from tools.get_nearby import get_nearby_restaurants
from db.supabase_client import supabase



llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)


# Prompt of the agent

# ── 2. SYSTEM PROMPT ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are VYBE, a friendly and concise food discovery assistant.

You help users find food based on cravings, diet, budget, calories, 
protein, group size, or location.

## How to use your tools
- Always call search_food for any food or dish related query.
- Call get_nearby_restaurants when the user mentions location, 
  "near me", or "nearby". Only show dishes from restaurants in both results.
- If the user refines a previous request remember the earlier context 
  and adjust your search accordingly.

## How to respond
- Keep responses short and friendly.
- Format each result as: Dish name · Restaurant · Price · Calories
- If no results found, suggest the user broaden their search.
- Never make up dishes or restaurants.

## User location
Default coordinates if not provided: lat=43.8971, lng=-78.8658
"""



# ── 3. BUILD AGENT ────────────────────────────────────────────────────────────

agent = create_agent(
    model=llm,
    tools=[search_food, get_nearby_restaurants],
    prompt=SYSTEM_PROMPT,
)




# ── 4. LOAD HISTORY FROM SUPABASE ─────────────────────────────────────────────
# We fetch the last 10 messages for this thread from Supabase.
# They come back as raw dicts so we convert them into LangChain
# message objects (HumanMessage / AIMessage) that the agent understands.
# Limiting to 10 keeps the context window small and costs low.


def load_history(thread_id:str)->list:
    response = (
        supabase.from_("chat_messages")
        .select("role, content")
         .eq("thread_id", thread_id)
        .order("created_at", desc=False)   # oldest first
        .limit(10)
        .execute()

    )


    messages = []
    for res in response.data:
        if res['role'] == 'user':
            messages.append(HumanMessage(content=res['content']))
        elif res['role'] == "assistant":
            messages.appned(AIMessage(content = res['content']))    
    return messages


# ── 5. SAVE MESSAGE TO SUPABASE ───────────────────────────────────────────────
# After every exchange we write both the user message and the
# assistant reply to Supabase as separate rows.
# This is what makes memory persist across restarts.

def save_message(thread_id: str, role: str, content: str):
    supabase.from_("chat_messages").insert({
        "thread_id": thread_id,
        "role": role,
        "content": content,
    }).execute()




# ── 6. CHAT FUNCTION ──────────────────────────────────────────────────────────
# This is the main function your app calls.
# Flow:
#   1. Load history from Supabase
#   2. Pass history + new message to agent
#   3. Save user message to Supabase
#   4. Save agent reply to Supabase
#   5. Return the reply


def chat(user_message:str, thread_id : str = "default")->str:
    history = load_history(thread_id)   #  Loading past history

    # invoking the agent
    response =  agent.invoke(input = user_message, chat_history = history)

    reply = response['output']


    # persist both sides of the exchange to Supabase
    save_message(thread_id, "user", user_message)
    save_message(thread_id, "assistant", reply)

    return reply




    

