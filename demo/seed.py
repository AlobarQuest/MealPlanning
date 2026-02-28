"""Seed the demo database with fake data if it's empty."""
from datetime import date, timedelta

from meal_planner.core import pantry as pantry_core, recipes as recipes_core
from meal_planner.core import meal_plan as mp_core, stores as stores_core
from meal_planner.core.meal_plan import get_week_start
from meal_planner.db.models import Store, PantryItem, Recipe, RecipeIngredient


DEMO_RECIPES = [
    Recipe(id=None, name="Spaghetti Bolognese", description="Classic Italian pasta",
           servings=4, prep_time="15 min", cook_time="45 min",
           tags="pasta,italian,dinner",
           instructions="1. Brown beef.\n2. Add tomato sauce.\n3. Simmer 30 min.\n4. Serve over pasta.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="ground beef", quantity=1, unit="lb"),
               RecipeIngredient(id=None, recipe_id=None, name="spaghetti", quantity=12, unit="oz"),
               RecipeIngredient(id=None, recipe_id=None, name="tomato sauce", quantity=24, unit="oz"),
               RecipeIngredient(id=None, recipe_id=None, name="onion", quantity=1, unit="medium"),
               RecipeIngredient(id=None, recipe_id=None, name="garlic", quantity=3, unit="cloves"),
           ]),
    Recipe(id=None, name="Chicken Stir Fry", description="Quick weeknight dinner",
           servings=2, prep_time="10 min", cook_time="15 min",
           tags="chicken,quick,asian,dinner",
           instructions="1. Slice chicken.\n2. Stir fry with vegetables.\n3. Add sauce.\n4. Serve with rice.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="chicken breast", quantity=1, unit="lb"),
               RecipeIngredient(id=None, recipe_id=None, name="broccoli", quantity=2, unit="cups"),
               RecipeIngredient(id=None, recipe_id=None, name="soy sauce", quantity=3, unit="tbsp"),
               RecipeIngredient(id=None, recipe_id=None, name="rice", quantity=1, unit="cup"),
           ]),
    Recipe(id=None, name="Avocado Toast", description="Quick healthy breakfast",
           servings=1, prep_time="5 min", cook_time="3 min",
           tags="breakfast,quick,vegetarian",
           instructions="1. Toast bread.\n2. Mash avocado.\n3. Top with seasoning.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="bread", quantity=2, unit="slices"),
               RecipeIngredient(id=None, recipe_id=None, name="avocado", quantity=1, unit="whole"),
           ]),
    Recipe(id=None, name="Greek Salad", description="Light Mediterranean salad",
           servings=2, prep_time="10 min", cook_time="0 min",
           tags="salad,vegetarian,lunch,mediterranean",
           instructions="1. Chop vegetables.\n2. Toss with feta and olives.\n3. Drizzle with olive oil.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="cucumber", quantity=1, unit="whole"),
               RecipeIngredient(id=None, recipe_id=None, name="tomatoes", quantity=2, unit="whole"),
               RecipeIngredient(id=None, recipe_id=None, name="feta cheese", quantity=4, unit="oz"),
               RecipeIngredient(id=None, recipe_id=None, name="kalamata olives", quantity=0.5, unit="cup"),
           ]),
    Recipe(id=None, name="Overnight Oats", description="Easy no-cook breakfast",
           servings=1, prep_time="5 min", cook_time="0 min",
           tags="breakfast,quick,vegetarian",
           instructions="1. Combine oats and milk.\n2. Add toppings.\n3. Refrigerate overnight.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="rolled oats", quantity=0.5, unit="cup"),
               RecipeIngredient(id=None, recipe_id=None, name="milk", quantity=0.5, unit="cup"),
               RecipeIngredient(id=None, recipe_id=None, name="honey", quantity=1, unit="tbsp"),
               RecipeIngredient(id=None, recipe_id=None, name="banana", quantity=1, unit="whole"),
           ]),
    Recipe(id=None, name="Black Bean Tacos", description="Easy meatless tacos",
           servings=4, prep_time="10 min", cook_time="10 min",
           tags="tacos,vegetarian,quick,dinner",
           instructions="1. Season beans.\n2. Warm tortillas.\n3. Assemble with toppings.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="black beans", quantity=2, unit="cans"),
               RecipeIngredient(id=None, recipe_id=None, name="corn tortillas", quantity=8, unit="whole"),
               RecipeIngredient(id=None, recipe_id=None, name="salsa", quantity=0.5, unit="cup"),
               RecipeIngredient(id=None, recipe_id=None, name="shredded cheese", quantity=1, unit="cup"),
           ]),
]

DEMO_PANTRY = [
    PantryItem(id=None, name="Chicken Breast", category="Meat", location="Freezer",
               quantity=3, unit="lbs", best_by="2026-04-01"),
    PantryItem(id=None, name="Pasta", category="Dry Goods", location="Pantry",
               quantity=2, unit="lbs"),
    PantryItem(id=None, name="Canned Tomatoes", category="Canned Goods", location="Pantry",
               quantity=4, unit="cans"),
    PantryItem(id=None, name="Greek Yogurt", category="Dairy", location="Fridge",
               quantity=1, unit="container", best_by="2026-03-05"),
    PantryItem(id=None, name="Eggs", category="Dairy", location="Fridge",
               quantity=12, unit="count", best_by="2026-03-10"),
    PantryItem(id=None, name="Rolled Oats", category="Dry Goods", location="Pantry",
               quantity=3, unit="lbs"),
    PantryItem(id=None, name="Black Beans", category="Canned Goods", location="Pantry",
               quantity=6, unit="cans"),
    PantryItem(id=None, name="Rice", category="Dry Goods", location="Pantry",
               quantity=5, unit="lbs"),
    PantryItem(id=None, name="Olive Oil", category="Condiments", location="Pantry",
               quantity=1, unit="bottle"),
    PantryItem(id=None, name="Avocados", category="Produce", location="Fridge",
               quantity=3, unit="whole", best_by="2026-03-04"),
]


def seed_if_empty():
    """Seed demo DB if it has no recipes yet."""
    if recipes_core.get_all():
        return  # Already seeded

    # Add a store
    store_id = stores_core.add(Store(id=None, name="Demo Grocery", location="123 Main St"))

    # Add recipes
    recipe_ids = [recipes_core.add(recipe) for recipe in DEMO_RECIPES]

    # Add pantry items
    for item in DEMO_PANTRY:
        item.preferred_store_id = store_id
        pantry_core.add(item)

    # Seed meal plan for current week
    week_start = get_week_start()
    slots = ["Breakfast", "Lunch", "Dinner"]
    for day_offset in range(7):
        day = week_start + timedelta(days=day_offset)
        for slot_idx, slot in enumerate(slots):
            rid = recipe_ids[(day_offset * 3 + slot_idx) % len(recipe_ids)]
            mp_core.set_meal(str(day), slot, rid, servings=1)
