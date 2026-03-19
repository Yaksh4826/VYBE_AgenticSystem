
import json
from datetime import datetime
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Optional
from db.supabase_client import supabase


# ── 1. INPUT SCHEMA ───────────────────────────────────────────────────────────
# user_lat and user_lng come from the frontend (device GPS).
# In terminal testing we hardcode them — later your app passes them in.

class GetNearbyInput(BaseModel):
    user_lat: float = Field(
        ...,                        # ... means required, no default
        description="User's current latitude e.g. 43.8971"
    )
    user_lng: float = Field(
        ...,
        description="User's current longitude e.g. -78.8658"
    )
    radius_km: float = Field(
        default=5.0,
        description="Search radius in kilometers, default is 5km"
    )
    open_now: Optional[bool] = Field(
        None,
        description="If True, only return currently open restaurants"
    )


# ── 2. THE TOOL ───────────────────────────────────────────────────────────────

@tool(args_schema=GetNearbyInput)
def get_nearby_restaurants(
    user_lat: float,
    user_lng: float,
    radius_km: float = 5.0,
    open_now: Optional[bool] = None,
) -> str:
    """
    Find restaurants near the user sorted by distance.
    Call this whenever the user mentions location, 'near me', or 'nearby'.
    Returns restaurants with distance in meters from the user.
    """

    # ── 3. CALL THE POSTGIS RPC FUNCTION ─────────────────────────────────────
    # rpc() calls the SQL function we created in Supabase.
    # It handles all the geo math — we just pass lat, lng, radius.

    response = supabase.rpc(
        "restaurants_nearby",
        {
            "lat": user_lat,
            "lng": user_lng,
            "radius_meters": radius_km * 1000   # convert km to meters
        }
    ).execute()

    # ── 4. HANDLE NO LOCATION DATA YET ───────────────────────────────────────
    # Since you haven't populated location data yet, we fall back to
    # returning all restaurants sorted by name instead of distance.
    # Once you populate location, this fallback never triggers.

    if not response.data:
        print("[INFO] No location data found — falling back to all restaurants")

        fallback = supabase.from_("restaurants") \
            .select("id, name, category, address, opening_time, closing_time") \
            .limit(10) \
            .execute()

        if not fallback.data:
            return "No restaurants found."

        results = fallback.data

        # tag them so the agent knows distance isn't real
        for r in results:
            r["distance_meters"] = None
            r["note"] = "Location not available yet"

    else:
        results = response.data

    # ── 5. OPEN NOW FILTER ────────────────────────────────────────────────────
    # Same approach as search_food — filter in Python after fetching.

    if open_now:
        now = datetime.now().strftime("%H:%M:%S")
        results = [
            r for r in results
            if r.get("opening_time") and r.get("closing_time")
            and r["opening_time"] <= now
            and r["closing_time"] >= now
        ]
        if not results:
            return "No restaurants are currently open in that area."

    # ── 6. FORMAT OUTPUT ──────────────────────────────────────────────────────
    # Convert distance to km for readability.
    # Agent uses this list to cross-reference with search_food results.

    formatted = []
    for r in results:
        distance = r.get("distance_meters")
        formatted.append({
            "restaurant_id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "address": r["address"],
            "opening_time": r["opening_time"],
            "closing_time": r["closing_time"],
            "distance": f"{round(distance / 1000, 2)} km away" if distance else "Distance unavailable",
        })

    return json.dumps(formatted, indent=2)