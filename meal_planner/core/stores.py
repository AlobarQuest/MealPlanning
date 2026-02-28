"""Store management — CRUD operations for the stores table.

Stores have a name, optional location, and optional notes.
Deleting a store nullifies any pantry items that reference it.
"""

from typing import Optional

from meal_planner.db.database import get_connection
from meal_planner.db.models import Store


def get_all() -> list[Store]:
    """Return all stores sorted alphabetically by name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM stores ORDER BY name").fetchall()
        return [Store(**dict(row)) for row in rows]
    finally:
        conn.close()


def get(store_id: int) -> Optional[Store]:
    """Return a single store by ID, or None if not found."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
        return Store(**dict(row)) if row else None
    finally:
        conn.close()


def add(store: Store) -> int:
    """Insert a new store and return its ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO stores (name, location, notes) VALUES (?, ?, ?)",
            (store.name, store.location, store.notes),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update(store: Store) -> None:
    """Update an existing store by its ID."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE stores SET name=?, location=?, notes=? WHERE id=?",
            (store.name, store.location, store.notes, store.id),
        )
        conn.commit()
    finally:
        conn.close()


def delete(store_id: int) -> None:
    """Delete a store by ID. Nullifies pantry items that reference it first."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE pantry SET preferred_store_id = NULL WHERE preferred_store_id = ?",
            (store_id,),
        )
        conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
        conn.commit()
    finally:
        conn.close()
