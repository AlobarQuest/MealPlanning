"""Recipe library CRUD — create, read, search, update, and delete recipes.

Each recipe has an embedded list of RecipeIngredient items.  On update, all
existing ingredients are deleted and replaced with the new set.
"""

from typing import Optional

from meal_planner.db.database import get_connection
from meal_planner.db.models import Recipe, RecipeIngredient


def _row_to_recipe(row, conn) -> Recipe:
    """Convert a database row into a Recipe, loading its ingredients."""
    recipe = Recipe(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        servings=row["servings"],
        prep_time=row["prep_time"],
        cook_time=row["cook_time"],
        instructions=row["instructions"],
        source_url=row["source_url"],
        tags=row["tags"],
        rating=row["rating"],
        created_at=row["created_at"],
    )
    ing_rows = conn.execute(
        "SELECT * FROM recipe_ingredients WHERE recipe_id = ? ORDER BY id",
        (recipe.id,),
    ).fetchall()
    recipe.ingredients = [
        RecipeIngredient(
            id=r["id"],
            recipe_id=r["recipe_id"],
            name=r["name"],
            quantity=r["quantity"],
            unit=r["unit"],
            estimated_price=r["estimated_price"],
            shopping_name=r["shopping_name"],
            shopping_qty=r["shopping_qty"],
            shopping_unit=r["shopping_unit"],
        )
        for r in ing_rows
    ]
    return recipe


def get_all() -> list[Recipe]:
    """Return all recipes sorted alphabetically by name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM recipes ORDER BY name").fetchall()
        return [_row_to_recipe(r, conn) for r in rows]
    finally:
        conn.close()


def get(recipe_id: int) -> Optional[Recipe]:
    """Return a single recipe with its ingredients, or None if not found."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        return _row_to_recipe(row, conn) if row else None
    finally:
        conn.close()


def search(query: str) -> list[Recipe]:
    """Return recipes whose name, description, or tags match the query (case-insensitive)."""
    conn = get_connection()
    try:
        pattern = f"%{query}%"
        rows = conn.execute(
            "SELECT * FROM recipes WHERE name LIKE ? OR description LIKE ? OR tags LIKE ? ORDER BY name",
            (pattern, pattern, pattern),
        ).fetchall()
        return [_row_to_recipe(r, conn) for r in rows]
    finally:
        conn.close()


def add(recipe: Recipe) -> int:
    """Insert a new recipe and its ingredients. Return the new recipe ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO recipes (name, description, servings, prep_time, cook_time,
               instructions, source_url, tags, rating)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                recipe.name, recipe.description, recipe.servings,
                recipe.prep_time, recipe.cook_time, recipe.instructions,
                recipe.source_url, recipe.tags, recipe.rating,
            ),
        )
        recipe_id = cursor.lastrowid
        for ing in recipe.ingredients:
            conn.execute(
                """INSERT INTO recipe_ingredients
                   (recipe_id, name, quantity, unit, estimated_price,
                    shopping_name, shopping_qty, shopping_unit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (recipe_id, ing.name, ing.quantity, ing.unit, ing.estimated_price,
                 ing.shopping_name, ing.shopping_qty, ing.shopping_unit),
            )
        conn.commit()
        return recipe_id
    finally:
        conn.close()


def update(recipe: Recipe) -> None:
    """Update a recipe's fields and replace all its ingredients."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE recipes SET name=?, description=?, servings=?, prep_time=?,
               cook_time=?, instructions=?, source_url=?, tags=?, rating=?
               WHERE id=?""",
            (
                recipe.name, recipe.description, recipe.servings,
                recipe.prep_time, recipe.cook_time, recipe.instructions,
                recipe.source_url, recipe.tags, recipe.rating, recipe.id,
            ),
        )
        conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe.id,))
        for ing in recipe.ingredients:
            conn.execute(
                """INSERT INTO recipe_ingredients
                   (recipe_id, name, quantity, unit, estimated_price,
                    shopping_name, shopping_qty, shopping_unit)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (recipe.id, ing.name, ing.quantity, ing.unit, ing.estimated_price,
                 ing.shopping_name, ing.shopping_qty, ing.shopping_unit),
            )
        conn.commit()
    finally:
        conn.close()


def delete(recipe_id: int) -> None:
    """Delete a recipe by ID. Ingredients are cascade-deleted by the DB."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()
    finally:
        conn.close()


def get_unnormalized_recipes() -> list[Recipe]:
    """Return recipes that have ingredients without normalized shopping fields."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT DISTINCT r.id FROM recipes r
               JOIN recipe_ingredients ri ON ri.recipe_id = r.id
               WHERE ri.shopping_name IS NULL"""
        ).fetchall()
        recipe_ids = [row["id"] for row in rows]
    finally:
        conn.close()
    recipes = []
    for rid in recipe_ids:
        recipe = get(rid)
        if recipe:
            recipes.append(recipe)
    return recipes
