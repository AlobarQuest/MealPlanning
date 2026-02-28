"""Known prices management — receipt-sourced grocery price data.

Prices in this table take priority over recipe ingredient prices and AI estimates
when calculating shopping list costs.
"""

from typing import Optional

from meal_planner.db.database import get_connection
from meal_planner.db.models import KnownPrice


def get_all() -> list[KnownPrice]:
    """Return all known prices sorted by item name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM known_prices ORDER BY item_name").fetchall()
        return [KnownPrice(**dict(row)) for row in rows]
    finally:
        conn.close()


def get_by_name(item_name: str) -> Optional[KnownPrice]:
    """Look up a known price by item name (case-insensitive)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM known_prices WHERE LOWER(item_name) = LOWER(?)",
            (item_name.strip(),),
        ).fetchone()
        return KnownPrice(**dict(row)) if row else None
    finally:
        conn.close()


def upsert(item_name: str, unit_price: float, unit: str = None, store_id: int = None) -> None:
    """Insert or update a known price entry."""
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM known_prices WHERE LOWER(item_name) = LOWER(?)",
            (item_name.strip(),),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE known_prices SET unit_price=?, unit=?, store_id=?,
                   last_updated=CURRENT_TIMESTAMP WHERE id=?""",
                (unit_price, unit, store_id, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO known_prices (item_name, unit_price, unit, store_id)
                   VALUES (?, ?, ?, ?)""",
                (item_name.strip(), unit_price, unit, store_id),
            )
        conn.commit()
    finally:
        conn.close()


def bulk_upsert(items: list[dict]) -> int:
    """Upsert multiple price entries. Each dict: {item_name, unit_price, unit, store_id}.
    Returns count of items processed."""
    conn = get_connection()
    try:
        count = 0
        for item in items:
            name = item["item_name"].strip()
            existing = conn.execute(
                "SELECT id FROM known_prices WHERE LOWER(item_name) = LOWER(?)",
                (name,),
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE known_prices SET unit_price=?, unit=?, store_id=?,
                       last_updated=CURRENT_TIMESTAMP WHERE id=?""",
                    (item["unit_price"], item.get("unit"), item.get("store_id"), existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO known_prices (item_name, unit_price, unit, store_id)
                       VALUES (?, ?, ?, ?)""",
                    (name, item["unit_price"], item.get("unit"), item.get("store_id")),
                )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def delete(price_id: int) -> None:
    """Delete a known price entry."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM known_prices WHERE id = ?", (price_id,))
        conn.commit()
    finally:
        conn.close()
