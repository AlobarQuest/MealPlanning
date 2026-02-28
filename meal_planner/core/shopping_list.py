"""Shopping list generation — aggregate recipe ingredients, subtract pantry stock, group by store.

The generate() function is the main entry point.  It sums ingredient quantities
across all planned meals in a date range, optionally subtracts what's already
on hand in the pantry, and returns results grouped by preferred store.
Each item now includes an estimated cost when price data is available.
"""

import json
from collections import defaultdict
from typing import Optional

from meal_planner.db.database import get_connection
from meal_planner.core.meal_plan import get_meals_in_range
from meal_planner.config import get_setting, set_setting

_CACHE_KEY = "saved_shopping_list"


def generate(start_date: str, end_date: str, use_pantry: bool = True) -> dict[str, list[tuple[str, float, str, Optional[float]]]]:
    """
    Generate a shopping list for the given date range.
    Returns {store_name: [(ingredient_name, quantity_needed, unit, estimated_cost), ...]}
    estimated_cost is unit_price * buy_qty if a price is known, else None.
    """
    entries = get_meals_in_range(start_date, end_date)
    if not entries:
        return {}

    # Aggregate required ingredients across all planned meals
    # key: (ingredient_name_lower, unit) -> total needed
    required: dict[tuple[str, str], float] = defaultdict(float)
    # Track per-ingredient prices from recipe_ingredients (recipe price takes priority)
    ingredient_prices: dict[tuple[str, str], float] = {}

    for entry in entries:
        if not entry.recipe_id:
            continue
        conn = get_connection()
        try:
            ings = conn.execute(
                """SELECT name, quantity, unit, estimated_price,
                          shopping_name, shopping_qty, shopping_unit
                   FROM recipe_ingredients WHERE recipe_id = ?""",
                (entry.recipe_id,),
            ).fetchall()
            for ing in ings:
                # Use normalized shopping fields when available, fall back to raw
                s_name = (ing["shopping_name"] or ing["name"]).lower().strip()
                s_unit = (ing["shopping_unit"] or ing["unit"] or "").lower().strip()
                s_qty = ing["shopping_qty"] if ing["shopping_qty"] is not None else (ing["quantity"] or 0)

                key = (s_name, s_unit)
                qty = s_qty * entry.servings
                required[key] += qty
                if ing["estimated_price"] is not None and key not in ingredient_prices:
                    ingredient_prices[key] = ing["estimated_price"]
        finally:
            conn.close()

    if not required:
        return {}

    # Build pantry lookup and determine quantities to buy
    conn = get_connection()
    try:
        pantry_rows = conn.execute(
            "SELECT name, quantity, estimated_price FROM pantry"
        ).fetchall()
        pantry_qty = {row["name"].lower().strip(): (row["quantity"] or 0) for row in pantry_rows}
        # Staples where user says "I have it" (need_to_buy=0) are excluded from shopping list
        staple_rows = conn.execute(
            "SELECT name FROM staples WHERE need_to_buy = 0"
        ).fetchall()
        staple_names = {row["name"].lower().strip() for row in staple_rows}
        # Pantry prices as fallback (keyed by name_lower only)
        pantry_prices: dict[str, float] = {}
        for row in pantry_rows:
            if row["estimated_price"] is not None:
                pantry_prices[row["name"].lower().strip()] = row["estimated_price"]

        # Load known prices (highest priority)
        known_price_rows = conn.execute(
            "SELECT item_name, unit_price FROM known_prices"
        ).fetchall()
        known_prices = {
            row["item_name"].lower().strip(): row["unit_price"]
            for row in known_price_rows
        }

        store_items: dict[str, list[tuple[str, float, str, Optional[float]]]] = defaultdict(list)

        for (ing_name, unit), needed in required.items():
            # Skip staple items — user always has these on hand
            if ing_name in staple_names:
                continue

            if use_pantry:
                on_hand = pantry_qty.get(ing_name, 0)
                buy_qty = needed - on_hand
                if buy_qty <= 0:
                    continue
            else:
                buy_qty = needed

            # Look up preferred store for this ingredient
            store_row = conn.execute(
                """SELECT s.name as store_name FROM pantry p
                   LEFT JOIN stores s ON p.preferred_store_id = s.id
                   WHERE LOWER(p.name) = ?
                   LIMIT 1""",
                (ing_name,),
            ).fetchone()
            store_name = store_row["store_name"] if store_row and store_row["store_name"] else "No Store Assigned"

            # Price resolution: known price > recipe ingredient price > pantry price > None
            unit_price = known_prices.get(ing_name)
            if unit_price is None:
                unit_price = ingredient_prices.get((ing_name, unit))
            if unit_price is None:
                unit_price = pantry_prices.get(ing_name)
            item_cost = round(unit_price * buy_qty, 2) if unit_price is not None else None

            display_name = ing_name.title()
            store_items[store_name].append((display_name, round(buy_qty, 2), unit, item_cost))

        # Sort items within each store
        for store in store_items:
            store_items[store].sort(key=lambda x: x[0])

        # Add staples that need to be bought
        staple_need_rows = conn.execute(
            """SELECT s.name, s.category, st.name as store_name
               FROM staples s
               LEFT JOIN stores st ON s.preferred_store_id = st.id
               WHERE s.need_to_buy = 1"""
        ).fetchall()
        for row in staple_need_rows:
            store = row["store_name"] or "Staples"
            # Check if this staple is already in the list from a recipe
            staple_lower = row["name"].lower().strip()
            already_listed = any(
                item[0].lower().strip() == staple_lower
                for items in store_items.values()
                for item in items
            )
            if not already_listed:
                staple_price = known_prices.get(staple_lower)
                store_items[store].append((row["name"], 0, "", staple_price))

        # Re-sort after adding staples
        for store in store_items:
            store_items[store].sort(key=lambda x: x[0])

        return dict(store_items)
    finally:
        conn.close()


def get_ingredient_sources(start_date: str, end_date: str) -> dict[str, list[tuple[int, str, str, str, float, str]]]:
    """Map each ingredient to the recipes that require it.

    Returns {ingredient_name_lower: [(recipe_id, recipe_name, date, meal_slot, qty, unit), ...]}
    """
    entries = get_meals_in_range(start_date, end_date)
    if not entries:
        return {}

    sources: dict[str, list[tuple[int, str, str, str, float, str]]] = defaultdict(list)

    for entry in entries:
        if not entry.recipe_id:
            continue
        conn = get_connection()
        try:
            ings = conn.execute(
                """SELECT name, quantity, unit, shopping_name, shopping_qty, shopping_unit
                   FROM recipe_ingredients WHERE recipe_id = ?""",
                (entry.recipe_id,),
            ).fetchall()
            for ing in ings:
                key = (ing["shopping_name"] or ing["name"]).lower().strip()
                qty = (ing["shopping_qty"] if ing["shopping_qty"] is not None else (ing["quantity"] or 0)) * entry.servings
                unit = (ing["shopping_unit"] or ing["unit"] or "").lower().strip()
                sources[key].append((
                    entry.recipe_id,
                    entry.recipe_name or "Unknown Recipe",
                    entry.date,
                    entry.meal_slot,
                    qty,
                    unit,
                ))
        finally:
            conn.close()

    return dict(sources)


def format_shopping_list(shopping_list: dict[str, list[tuple[str, float, str, Optional[float]]]]) -> str:
    """Format the shopping list as plain text for export/clipboard, including prices and totals."""
    if not shopping_list:
        return "No items needed."

    lines = []
    grand_total = 0.0
    grand_total_has_items = False

    for store, items in sorted(shopping_list.items()):
        lines.append(f"=== {store} ===")
        store_subtotal = 0.0
        store_has_priced = False

        for name, qty, unit, cost in items:
            parts = [f"  [ ] {name}"]
            if qty and qty > 0:
                qty_str = f"{qty:g} {unit}".strip()
                parts.append(f" — {qty_str}")
            if cost is not None:
                parts.append(f"  ${cost:.2f}")
                store_subtotal += cost
                store_has_priced = True
            lines.append("".join(parts))

        if store_has_priced:
            lines.append(f"  Store subtotal: ${store_subtotal:.2f}")
            grand_total += store_subtotal
            grand_total_has_items = True
        lines.append("")

    if grand_total_has_items:
        lines.append(f"Estimated total: ${grand_total:.2f}")

    return "\n".join(lines).strip()


def save_cached_list(shopping_data, ingredient_sources, start_date, end_date, use_pantry):
    """Persist the current shopping list state to the settings table as JSON."""
    payload = {
        "shopping_data": shopping_data,
        "ingredient_sources": ingredient_sources,
        "start_date": start_date,
        "end_date": end_date,
        "use_pantry": use_pantry,
    }
    set_setting(_CACHE_KEY, json.dumps(payload))


def load_cached_list() -> Optional[dict]:
    """Load the cached shopping list from settings.

    Returns a dict with keys shopping_data, ingredient_sources, start_date,
    end_date, use_pantry — or None if no cached list exists.
    """
    raw = get_setting(_CACHE_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        # Convert list-of-lists back to list-of-tuples for consistency
        for store in data.get("shopping_data", {}):
            data["shopping_data"][store] = [tuple(item) for item in data["shopping_data"][store]]
        # Validate ingredient_sources format: tuples must have 6 elements
        # (recipe_id, recipe_name, date, meal_slot, qty, unit).
        # Discard stale caches that used the old 5-element format.
        sources = data.get("ingredient_sources", {})
        valid_sources = {}
        for key, src_list in sources.items():
            converted = [tuple(src) for src in src_list]
            if converted and len(converted[0]) == 6:
                valid_sources[key] = converted
        data["ingredient_sources"] = valid_sources
        return data
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def clear_cached_list():
    """Remove the cached shopping list from settings."""
    set_setting(_CACHE_KEY, "")
