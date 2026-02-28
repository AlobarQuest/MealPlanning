"""Claude AI integration — recipe parsing, generation, modification, and meal plan suggestions.

All public functions call the Anthropic API using the key stored in the settings
table.  Responses are requested in JSON (matching RECIPE_SCHEMA) and parsed
into Recipe/RecipeIngredient dataclasses.  Long-running calls should be wrapped
in an AIWorker thread from the GUI layer to avoid blocking the UI.
"""

import json
import re
from typing import Optional

import httpx

from meal_planner.db.database import get_connection
from meal_planner.db.models import Recipe, RecipeIngredient


def _get_api_key() -> Optional[str]:
    """Retrieve the Claude API key from the settings table, or None if not set."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = 'claude_api_key'").fetchone()
        return row["value"] if row else None
    finally:
        conn.close()


def _get_client():
    """Create and return an Anthropic client. Raises ValueError if the API key is not set."""
    import anthropic
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("Claude API key not set. Go to File → Settings to add your API key.")
    return anthropic.Anthropic(api_key=api_key)


def _get_pantry_summary() -> str:
    """Build a brief pantry summary string to include in prompts."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name, brand, quantity, unit, category, location FROM pantry ORDER BY category, name"
        ).fetchall()
        if not rows:
            return "Pantry is empty."
        lines = []
        for r in rows:
            parts = [r["name"]]
            if r["brand"]:
                parts.append(f"({r['brand']})")
            qty = f"{r['quantity']:g}" if r["quantity"] else "?"
            if r["unit"]:
                qty += f" {r['unit']}"
            parts.append(f"— qty: {qty}")
            if r["location"]:
                parts.append(f"[{r['location']}]")
            lines.append(" ".join(parts))
        return "\n".join(lines)
    finally:
        conn.close()


def _parse_recipe_json(text: str) -> Optional[Recipe]:
    """Extract JSON from Claude's response and parse into Recipe."""
    # Try to find JSON block in response
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        json_str = match.group(1)
    else:
        # Try raw JSON
        json_str = text.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return None

    ingredients = [
        RecipeIngredient(
            id=None,
            recipe_id=None,
            name=ing.get("name", ""),
            quantity=ing.get("quantity"),
            unit=ing.get("unit"),
        )
        for ing in data.get("ingredients", [])
    ]

    rating = data.get("rating")
    if rating is not None:
        try:
            rating = max(1, min(5, int(rating)))
        except (ValueError, TypeError):
            rating = None

    return Recipe(
        id=None,
        name=data.get("name", "Untitled Recipe"),
        description=data.get("description"),
        servings=data.get("servings", 4),
        prep_time=data.get("prep_time"),
        cook_time=data.get("cook_time"),
        instructions=data.get("instructions"),
        source_url=data.get("source_url"),
        tags=data.get("tags"),
        rating=rating,
        ingredients=ingredients,
    )


# JSON schema template included in every AI prompt so Claude returns structured data.
RECIPE_SCHEMA = """
{
  "name": "Recipe Name",
  "description": "Brief description",
  "servings": 4,
  "prep_time": "15 minutes",
  "cook_time": "30 minutes",
  "tags": "chicken,quick,dinner",
  "rating": 4,
  "instructions": "Step 1...\\nStep 2...",
  "ingredients": [
    {"name": "chicken breast", "quantity": 2, "unit": "lbs"},
    {"name": "garlic", "quantity": 3, "unit": "cloves"}
  ]
}
"""


def parse_recipe_text(text: str) -> Optional[Recipe]:
    """Send raw recipe text to Claude and get back a structured Recipe."""
    client = _get_client()
    prompt = f"""Extract the recipe from the following text and return it as JSON matching this schema exactly:
{RECIPE_SCHEMA}

Recipe text:
{text}

Return only the JSON, wrapped in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_recipe_json(message.content[0].text)


def parse_recipe_url(url: str) -> Optional[Recipe]:
    """Fetch a URL and have Claude extract the recipe."""
    try:
        response = httpx.get(url, follow_redirects=True, timeout=15)
        response.raise_for_status()
        html = response.text
    except Exception as e:
        raise ValueError(f"Failed to fetch URL: {e}")

    # Strip down HTML to reduce token usage — keep text content
    # Remove script/style tags and their content
    clean = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", "", html, flags=re.IGNORECASE)
    # Remove all other HTML tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    # Truncate to avoid hitting token limits
    if len(clean) > 12000:
        clean = clean[:12000] + "..."

    client = _get_client()
    prompt = f"""Extract the recipe from the following web page content and return it as JSON matching this schema exactly:
{RECIPE_SCHEMA}

Also include "source_url": "{url}" in the JSON.

Page content:
{clean}

Return only the JSON, wrapped in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    recipe = _parse_recipe_json(message.content[0].text)
    if recipe:
        recipe.source_url = url
    return recipe


def generate_recipe(preferences: str = "") -> Optional[Recipe]:
    """Generate a recipe using current pantry contents."""
    pantry_summary = _get_pantry_summary()
    client = _get_client()

    extra = f"\n\nAdditional preferences or constraints: {preferences}" if preferences else ""
    prompt = f"""I have the following items in my pantry/fridge/freezer:

{pantry_summary}

Please create a recipe I can make using primarily these ingredients. Return it as JSON matching this schema exactly:
{RECIPE_SCHEMA}
{extra}

Return only the JSON, wrapped in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_recipe_json(message.content[0].text)


def _format_recipes_for_suggest(recipes) -> str:
    """Format recipe list with tags and ratings for the suggest_week prompt."""
    if not recipes:
        return "None saved yet"
    lines = []
    for r in recipes:
        parts = [f"- {r.name}"]
        if r.tags:
            parts.append(f"[{r.tags}]")
        if r.rating:
            parts.append(f"(rating: {r.rating}/5)")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def suggest_week(existing_recipes: list, preferences: str = "") -> list[dict]:
    """Suggest a full week of meals. Returns list of {date, slot, recipe_name, notes}."""
    pantry_summary = _get_pantry_summary()
    recipes_str = _format_recipes_for_suggest(existing_recipes)
    client = _get_client()

    extra = f"\n\nPreferences/constraints: {preferences}" if preferences else ""
    prompt = f"""Help me plan a week of meals (Monday through Sunday, with Breakfast, Lunch, and Dinner each day).

My pantry/fridge/freezer contains:
{pantry_summary}

My saved recipes include:
{recipes_str}

Prefer recipes with higher ratings (4-5 stars). Consider tags when planning — use 'breakfast' tagged recipes for breakfast slots, respect dietary tags like 'vegetarian', 'gluten-free', etc.

You can suggest meals from my saved recipes, simple meals using pantry items, or new recipe ideas.
Return a JSON array like this:
```json
[
  {{"day": "Monday", "slot": "Breakfast", "meal": "Oatmeal with fruit", "notes": "Use pantry oats"}},
  {{"day": "Monday", "slot": "Lunch", "meal": "...", "notes": "..."}},
  ...
]
```
{extra}

Return only the JSON array, wrapped in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return []


def estimate_prices(items: list[tuple[str, float, str]]) -> dict[str, float]:
    """Estimate current US grocery unit prices for a list of ingredients.

    Takes a list of (name, qty, unit) tuples from the shopping list.
    Returns {name_lower: estimated_unit_price} dict.
    """
    client = _get_client()

    # Build a structured list with explicit keys the AI must use
    item_lines = []
    expected_keys = []
    for name, qty, unit in items:
        key = name.lower().strip()
        expected_keys.append(key)
        unit_str = f" per {unit}" if unit else " per unit"
        item_lines.append(f'  "{key}": <price{unit_str}>')

    items_template = ",\n".join(item_lines)

    prompt = f"""Estimate current US grocery store prices for these ingredients.
Return a JSON object with EXACTLY these keys and a numeric price value for each.

Fill in this template:
```json
{{
{items_template}
}}
```

Prices should be per the unit shown (e.g. per lb, per cup, per clove).
Replace each <price...> with a realistic number. Return only the filled-in JSON in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        json_str = match.group(1)
    else:
        # Fallback: try parsing the entire response as JSON
        json_str = text.strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        return {}

    # Validate: only keep positive numeric values
    result = {}
    for key, val in data.items():
        try:
            price = float(val)
            if price > 0:
                result[key.lower().strip()] = price
        except (ValueError, TypeError):
            continue
    return result


def normalize_ingredients(ingredients: list[RecipeIngredient]) -> list[dict]:
    """Normalize recipe ingredients into purchasable shopping form.

    Takes a list of RecipeIngredient and returns a list of dicts:
    [{"shopping_name": str, "shopping_qty": float|None, "shopping_unit": str|None}, ...]

    The AI strips preparation instructions (drained, minced, divided, room temperature),
    converts recipe amounts to purchase units (30oz -> 2 cans), and preserves qualifiers
    that affect what to buy (canned, dry, fresh, frozen).
    """
    if not ingredients:
        return []

    client = _get_client()

    ing_lines = []
    for i, ing in enumerate(ingredients):
        qty_str = f"{ing.quantity:g}" if ing.quantity else "?"
        unit_str = ing.unit or ""
        ing_lines.append(f'{i}. {qty_str} {unit_str} {ing.name}'.strip())

    ingredients_text = "\n".join(ing_lines)

    prompt = f"""Convert these recipe ingredients into their purchasable shopping form.

For each ingredient:
1. Strip preparation instructions (drained, minced, divided, chopped, room temperature, etc.)
2. Convert to how the item is purchased (e.g. "30oz black beans drained" -> "canned black beans", qty 2, unit "15oz cans")
3. Keep qualifiers that affect what you buy: canned, dry, fresh, frozen, whole, ground, etc.
4. Use common grocery units: lbs, oz, each, bunch, cans, bags, bottles, etc.
5. Normalize the name to a common grocery name (e.g. "garlic cloves" -> "garlic")

Recipe ingredients:
{ingredients_text}

Return a JSON array with one entry per ingredient (same order), matching this schema:
```json
[
  {{"index": 0, "shopping_name": "chicken breast", "shopping_qty": 2, "shopping_unit": "lbs"}},
  {{"index": 1, "shopping_name": "garlic", "shopping_qty": 1, "shopping_unit": "head"}}
]
```

Return only the JSON array, wrapped in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    # Build result list aligned to input order
    result = []
    data_by_index = {item.get("index", i): item for i, item in enumerate(data)}
    for i in range(len(ingredients)):
        item = data_by_index.get(i, {})
        result.append({
            "shopping_name": item.get("shopping_name"),
            "shopping_qty": item.get("shopping_qty"),
            "shopping_unit": item.get("shopping_unit"),
        })

    return result


def parse_receipt_image(image_paths: list[str]) -> list[dict]:
    """Extract item names and prices from receipt photo(s).

    Takes a list of file paths to receipt images (JPG/PNG).
    Returns list of dicts: [{"item_name": str, "total_price": float, "quantity": int, "unit_price": float}, ...]
    """
    if not image_paths:
        return []

    import base64
    from pathlib import Path

    client = _get_client()

    content = []
    for path in image_paths:
        p = Path(path)
        suffix = p.suffix.lower()
        media_type = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        with open(p, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        })

    content.append({
        "type": "text",
        "text": """Extract all grocery items and their prices from this receipt.

For each item, provide:
- item_name: the product name (simplified to a common grocery name, e.g. "BLK BEANS 15OZ" -> "canned black beans")
- price: the total price paid for this item
- quantity: how many were purchased (default 1 if not clear)

Return a JSON array:
```json
[
  {"item_name": "canned black beans", "price": 1.29, "quantity": 2},
  {"item_name": "whole milk", "price": 4.99, "quantity": 1}
]
```

Ignore tax lines, subtotals, totals, and non-grocery items (bags, coupons, etc.).
Return only the JSON array, wrapped in ```json``` code fences."""
    })

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=4096,
        messages=[{"role": "user", "content": content}],
    )

    text = message.content[0].text
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    # Validate and compute unit prices
    results = []
    for item in data:
        try:
            name = item.get("item_name", "").strip()
            price = float(item.get("price", 0))
            qty = int(item.get("quantity", 1))
            if name and price > 0 and qty > 0:
                results.append({
                    "item_name": name,
                    "total_price": price,
                    "quantity": qty,
                    "unit_price": round(price / qty, 2),
                })
        except (ValueError, TypeError):
            continue

    return results


def modify_recipe(recipe: Recipe, instruction: str) -> Optional[Recipe]:
    """Modify an existing recipe per user instruction."""
    ingredients_str = "\n".join(
        f"- {ing.quantity or ''} {ing.unit or ''} {ing.name}".strip()
        for ing in recipe.ingredients
    )
    client = _get_client()

    prompt = f"""Modify the following recipe according to this instruction: {instruction}

Current recipe:
Name: {recipe.name}
Servings: {recipe.servings}
Prep time: {recipe.prep_time}
Cook time: {recipe.cook_time}
Description: {recipe.description}
Tags: {recipe.tags}

Ingredients:
{ingredients_str}

Instructions:
{recipe.instructions}

Return the modified recipe as JSON matching this schema exactly:
{RECIPE_SCHEMA}

Return only the JSON, wrapped in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    modified = _parse_recipe_json(message.content[0].text)
    if modified:
        if recipe.source_url:
            modified.source_url = recipe.source_url
        # Carry forward estimated_price from original ingredients by matching name
        price_map = {
            ing.name.lower().strip(): ing.estimated_price
            for ing in recipe.ingredients
            if ing.estimated_price is not None
        }
        for ing in modified.ingredients:
            price = price_map.get(ing.name.lower().strip())
            if price is not None:
                ing.estimated_price = price
    return modified


PREDEFINED_TAGS = (
    "easy,quick,budget-friendly,comfort food,healthy,vegetarian,vegan,"
    "gluten-free,dairy-free,high-protein,meal-prep,kid-friendly,one-pot,"
    "slow-cooker,grilling,breakfast,lunch,dinner,snack,dessert,side-dish,"
    "soup,salad,favorite"
)


def bulk_generate_recipes(count: int = 5, preferences: str = "") -> list[Recipe]:
    """Generate multiple recipes in a single API call. Returns list of Recipe objects."""
    pantry_summary = _get_pantry_summary()
    client = _get_client()

    extra = f"\n\nAdditional preferences: {preferences}" if preferences else ""
    prompt = f"""Generate exactly {count} different recipes. Use a variety of meal types (breakfast, lunch, dinner, snacks).

My pantry/fridge/freezer contains:
{pantry_summary}

For tags, pick from this predefined list (comma-separated): {PREDEFINED_TAGS}
You may also add custom tags if needed.

Each recipe should include a rating from 1-5 (how good/recommended the recipe is).

Return a JSON array of {count} recipe objects, each matching this schema:
{RECIPE_SCHEMA}
{extra}

Return only the JSON array, wrapped in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        data = [data]

    recipes = []
    for item in data:
        try:
            ingredients = [
                RecipeIngredient(
                    id=None, recipe_id=None,
                    name=ing.get("name", ""),
                    quantity=ing.get("quantity"),
                    unit=ing.get("unit"),
                )
                for ing in item.get("ingredients", [])
            ]
            rating = item.get("rating")
            if rating is not None:
                try:
                    rating = max(1, min(5, int(rating)))
                except (ValueError, TypeError):
                    rating = None
            recipes.append(Recipe(
                id=None,
                name=item.get("name", "Untitled Recipe"),
                description=item.get("description"),
                servings=item.get("servings", 4),
                prep_time=item.get("prep_time"),
                cook_time=item.get("cook_time"),
                instructions=item.get("instructions"),
                source_url=item.get("source_url"),
                tags=item.get("tags"),
                rating=rating,
                ingredients=ingredients,
            ))
        except Exception:
            continue  # Skip entries that fail to parse
    return recipes
