"""Staples management — CRUD for persistent always-on-hand items.

Staples are independent of pantry inventory. Each staple has a need_to_buy
toggle; items marked as needed appear on shopping lists.
"""

from typing import Optional

from meal_planner.db.database import get_connection
from meal_planner.db.models import Staple


def get_all() -> list[Staple]:
    """Return all staples sorted by name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM staples ORDER BY name").fetchall()
        return [Staple(**dict(row)) for row in rows]
    finally:
        conn.close()


def get(staple_id: int) -> Optional[Staple]:
    """Return a single staple by ID."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM staples WHERE id = ?", (staple_id,)).fetchone()
        return Staple(**dict(row)) if row else None
    finally:
        conn.close()


def get_by_name(name: str) -> Optional[Staple]:
    """Return a staple by exact name (case-insensitive)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM staples WHERE LOWER(name) = LOWER(?)", (name.strip(),)
        ).fetchone()
        return Staple(**dict(row)) if row else None
    finally:
        conn.close()


def add(staple: Staple) -> int:
    """Insert a new staple. Return the new ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO staples (name, category, preferred_store_id, need_to_buy)
               VALUES (?, ?, ?, ?)""",
            (staple.name, staple.category, staple.preferred_store_id,
             int(staple.need_to_buy)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update(staple: Staple) -> None:
    """Update an existing staple."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE staples SET name=?, category=?, preferred_store_id=?,
               need_to_buy=? WHERE id=?""",
            (staple.name, staple.category, staple.preferred_store_id,
             int(staple.need_to_buy), staple.id),
        )
        conn.commit()
    finally:
        conn.close()


def delete(staple_id: int) -> None:
    """Delete a staple by ID."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM staples WHERE id = ?", (staple_id,))
        conn.commit()
    finally:
        conn.close()


def set_need_to_buy(staple_id: int, need: bool) -> None:
    """Toggle the need_to_buy flag for a staple."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE staples SET need_to_buy = ? WHERE id = ?",
            (int(need), staple_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_needed() -> list[Staple]:
    """Return all staples where need_to_buy is True."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM staples WHERE need_to_buy = 1 ORDER BY name"
        ).fetchall()
        return [Staple(**dict(row)) for row in rows]
    finally:
        conn.close()
