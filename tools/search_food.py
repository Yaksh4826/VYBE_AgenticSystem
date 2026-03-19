from langchain_core.tools import tool
import json
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional
from db.supabase_client import  supabase

""" It tells agent what input does this tool can take , paramters it can take """
class SearchFoodInput(BaseModel):
    query: Optional[str] =  Field(None, description="Free text search e.g. 'cheesy', 'spicy noodles', 'grilled chicken'"
    ) ,
    diet: Optional[List[str]] = Field(
        None,
        description="Dietary filters e.g. ['vegan'], ['gluten-free'], ['halal']"
    )
    max_price: Optional[float] = Field(
        None,
        description="Maximum price per dish in dollars e.g. 10.0 for 'under $10'"
    )
    max_calories: Optional[float] = Field(
        None,
        description="Maximum calories per dish e.g. 500 for 'under 500 calories'"
    )
    min_protein: Optional[float] = Field(
        None,
        description="Minimum protein in grams e.g. 30 for 'high protein meals'"
    )
    group_size: Optional[int] = Field(
        None,
        description="Party size e.g. 50 for 'food for a party of 50 people'"
    )
    open_now: Optional[bool] = Field(
        None,
        description="If True, only return dishes from currently open restaurants"
    )
 


@tool(args_schema= SearchFoodInput)
def search_food(query: Optional[str] = None,
    diet: Optional[List[str]] = None,
    max_price: Optional[float] = None,
    max_calories: Optional[float] = None,
    min_protein: Optional[float] = None,
    group_size: Optional[int] = None,
    open_now: Optional[bool] = None,
) -> str:
     """
    Search for food dishes based on the user's request.
    Use this for any food-related query including cravings, dietary needs,
    budget, calories, protein goals, or group/catering orders.
    """
       # ── 3. BUILD THE QUERY ────────────────────────────────────────────────────
    # We start with a base query selecting dish fields + the related restaurant.
    # The restaurants(...) part is a Supabase join — it pulls restaurant name
    # and hours alongside each dish automatically.
     
     q = (
        supabase
        .from_("food_dishes")
        .select("""
            id,
            name,
            price,
            calories,
            proteins_g,
            allergens,
            spicy_level,
            restaurants (
                id,
                name,
                opening_time,
                closing_time
            )
        """)
        .eq("is_available", True)
    )

    # ── 4. APPLY FILTERS ─────────────────────────────────────────────────────
    # Each filter only applies if the agent passed that param.
    # This is why all params are Optional — unused ones are simply skipped.

     if max_price is not None:
        q = q.lte("price", max_price)          # lte = less than or equal

     if max_calories is not None:
        q = q.lte("calories", max_calories)

     if min_protein is not None:
        q = q.gte("proteins_g", min_protein)   # gte = greater than or equal

    # Group size over 10 → look for catering/bulk items
     if group_size is not None and group_size > 10:
        q = q.eq("is_group_item", True)

    # Diet filters work by EXCLUDING dishes that contain that allergen.
    # cs means "contains" in Supabase array syntax — we use not() to invert it.
     if diet:
        for d in diet:
            q = q.not_.contains("allergens", [d])

    # ── 5. OPEN NOW FILTER ────────────────────────────────────────────────────
    # We compare current time against the restaurant's opening/closing hours.
    # Supabase can't filter on a joined table's columns directly,
    # so we do this filter in Python after fetching results.

     response = q.limit(10).execute()

     if not response.data:
        return "No dishes found matching those criteria. Try broadening the search."

     results = response.data

     if open_now:
        now = datetime.now().strftime("%H:%M:%S")
        results = [
            dish for dish in results
            if dish.get("restaurants")
            and dish["restaurants"]["opening_time"] <= now
            and dish["restaurants"]["closing_time"] >= now
        ]
        if not results:
            return "No dishes found from currently open restaurants."

    # ── 6. FORMAT OUTPUT ──────────────────────────────────────────────────────
    # We return a clean string the agent can read and present to the user.
    # JSON works well here — the agent formats it into a friendly response.

     formatted = []
     for dish in results:
        restaurant_name = dish["restaurants"]["name"] if dish.get("restaurants") else "Unknown"
        formatted.append({
            "dish": dish["name"],
            "restaurant": restaurant_name,
            "price": f"${dish['price']}",
            "calories": dish.get("calories", "N/A"),
            "protein_g": dish.get("proteins_g", "N/A"),
            "spicy_level": dish.get("spicy_level", 0),
            "allergens": dish.get("allergens", []),
        })

     return json.dumps(formatted, indent=2)