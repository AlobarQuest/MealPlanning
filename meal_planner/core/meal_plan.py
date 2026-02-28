"""Weekly meal planning — assign recipes to date + meal-slot combinations.

The meal plan is a sparse grid: only cells with an assigned recipe have rows
in the meal_plan table.  Weeks start on Monday and contain four slots per day.
"""

from datetime import date, timedelta
from typing import Optional

from meal_planner.db.database import get_connection
from meal_planner.db.models import MealPlanEntry

MEAL_SLOTS = ["Breakfast", "Lunch", "Dinner", "Snack"]


def get_week_start(for_date: date = None) -> date:
    """Returns the Monday of the week containing for_date."""
    if for_date is None:
        for_date = date.today()
    return for_date - timedelta(days=for_date.weekday())


def get_week(start_date: date) -> dict[str, dict[str, MealPlanEntry]]:
    """Returns meal plan for a week as {date_str: {slot: MealPlanEntry}}."""
    conn = get_connection()
    try:
        week_dates = [start_date + timedelta(days=i) for i in range(7)]
        date_strs = [d.isoformat() for d in week_dates]

        rows = conn.execute(
            """SELECT mp.*, r.name as recipe_name
               FROM meal_plan mp
               LEFT JOIN recipes r ON mp.recipe_id = r.id
               WHERE mp.date IN ({})
               ORDER BY mp.date, mp.meal_slot""".format(",".join("?" * 7)),
            date_strs,
        ).fetchall()

        # Build empty grid
        result = {d: {slot: None for slot in MEAL_SLOTS} for d in date_strs}

        for row in rows:
            entry = MealPlanEntry(
                id=row["id"],
                date=row["date"],
                meal_slot=row["meal_slot"],
                recipe_id=row["recipe_id"],
                servings=row["servings"],
                notes=row["notes"],
                recipe_name=row["recipe_name"],
            )
            if row["date"] in result and row["meal_slot"] in result[row["date"]]:
                result[row["date"]][row["meal_slot"]] = entry

        return result
    finally:
        conn.close()


def set_meal(entry_date: str, slot: str, recipe_id: Optional[int], servings: int = 1, notes: str = None) -> None:
    """Insert, update, or delete a meal plan entry.

    If recipe_id is None and notes is empty/None, the entry is deleted (or
    ignored if it doesn't exist).  If recipe_id is None but notes is non-empty,
    the entry is kept as a manual meal (e.g. "Leftovers", "Eat out").
    """
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM meal_plan WHERE date = ? AND meal_slot = ?",
            (entry_date, slot),
        ).fetchone()

        has_content = recipe_id is not None or bool(notes)

        if existing:
            if has_content:
                conn.execute(
                    "UPDATE meal_plan SET recipe_id=?, servings=?, notes=? WHERE date=? AND meal_slot=?",
                    (recipe_id, servings, notes, entry_date, slot),
                )
            else:
                conn.execute(
                    "DELETE FROM meal_plan WHERE date = ? AND meal_slot = ?",
                    (entry_date, slot),
                )
        elif has_content:
            conn.execute(
                "INSERT INTO meal_plan (date, meal_slot, recipe_id, servings, notes) VALUES (?, ?, ?, ?, ?)",
                (entry_date, slot, recipe_id, servings, notes),
            )
        conn.commit()
    finally:
        conn.close()


def clear_meal(entry_date: str, slot: str) -> None:
    """Remove the meal assignment for a date+slot. Convenience wrapper around set_meal."""
    set_meal(entry_date, slot, None)


def get_meals_in_range(start: str, end: str) -> list[MealPlanEntry]:
    """Returns all meal plan entries between start and end dates (inclusive)."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT mp.*, r.name as recipe_name
               FROM meal_plan mp
               LEFT JOIN recipes r ON mp.recipe_id = r.id
               WHERE mp.date >= ? AND mp.date <= ?
               ORDER BY mp.date, mp.meal_slot""",
            (start, end),
        ).fetchall()
        return [
            MealPlanEntry(
                id=row["id"],
                date=row["date"],
                meal_slot=row["meal_slot"],
                recipe_id=row["recipe_id"],
                servings=row["servings"],
                notes=row["notes"],
                recipe_name=row["recipe_name"],
            )
            for row in rows
        ]
    finally:
        conn.close()
