from tools.search_food import search_food
from tools.get_nearby import get_nearby_restaurants
# ── TEST A: Call the tool directly (no LLM involved) ─────────────────────────
# Great for checking your Supabase connection and query logic first.
# If this fails, the problem is in the tool or DB — not the agent.

# ── TEST A: Direct tool call ──────────────────────────────────────────────────
print("=" * 50)
print("DIRECT NEARBY TOOL TEST")
print("=" * 50)

# Using Oshawa, Ontario coordinates for testing
result = get_nearby_restaurants.invoke({
    "user_lat": 43.8971,
    "user_lng": -78.8658,
    "radius_km": 5.0
})
print(result)