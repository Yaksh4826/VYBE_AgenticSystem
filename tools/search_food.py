from typing import Optional
from pydantic import BaseModel
from langchain_core.tools import tool
import json
from datetime import datetime
from db.supabase_client import supabase


class SearchFoodInput(BaseModel):
    query: Optional[str] = None
    max_price: Optional[float] = None
    max_calories: Optional[float] = None
    min_protein: Optional[float] = None
    group_size: Optional[int] = None
    open_now: Optional[bool] = None
    exclude_allergen: Optional[str] = None    # ← replaces diet e.g. "gluten"
    is_vegan: Optional[bool] = None           # ← simple bool Groq handles fine


@tool(args_schema=SearchFoodInput)
def search_food(
    query: Optional[str] = None,
    max_price: Optional[float] = None,
    max_calories: Optional[float] = None,
    min_protein: Optional[float] = None,
    group_size: Optional[int] = None,
    open_now: Optional[bool] = None,
    exclude_allergen: Optional[str] = None,
    is_vegan: Optional[bool] = None,
) -> str:
    """
    Search for food dishes based on the user's request.
    Use this for any food-related query including cravings, dietary needs,
    budget, calories, protein goals, or group/catering orders.
    """

    q = (
        supabase
        .from_("food_dishes")
        .select("""
            id, name, price, calories, proteins_g,
            allergens, spicy_level,
            restaurants ( id, name, opening_time, closing_time )
        """)
        .eq("is_available", True)
    )

    if max_price is not None:
        q = q.lte("price", max_price)

    if max_calories is not None:
        q = q.lte("calories", max_calories)

    if min_protein is not None:
        q = q.gte("proteins_g", min_protein)

    if group_size is not None and group_size > 10:
        q = q.eq("is_group_item", True)

    # single allergen exclusion — no more List[str]
    if exclude_allergen:
        q = q.not_.contains("allergens", [exclude_allergen])

    # vegan = exclude dairy, gluten, eggs, fish all at once
    if is_vegan:
        for allergen in ["dairy", "eggs", "fish", "meat"]:
            q = q.not_.contains("allergens", [allergen])

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
        })

    return json.dumps(formatted, indent=2)