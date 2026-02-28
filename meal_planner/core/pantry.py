"""Pantry inventory management — CRUD operations and PantryChecker CSV import.

Items are matched during CSV import by barcode first, then by name+brand.
Stores referenced in CSV rows are auto-created in the stores table.
"""

import csv
from pathlib import Path
from typing import Optional
from datetime import date, timedelta

from meal_planner.db.database import get_connection
from meal_planner.db.models import PantryItem, Store


def _get_or_create_store(conn, store_name: str) -> Optional[int]:
    """Return the store ID for store_name, creating the store if it doesn't exist."""
    if not store_name or not store_name.strip():
        return None
    name = store_name.strip()
    row = conn.execute("SELECT id FROM stores WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute("INSERT INTO stores (name) VALUES (?)", (name,))
    return cursor.lastrowid


def import_csv(filepath: str) -> tuple[int, int]:
    """Import PantryChecker CSV. Returns (inserted, updated) counts."""
    inserted = 0
    updated = 0
    path = Path(filepath)

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        conn = get_connection()
        try:
            for row in reader:
                name = row.get("Name", "").strip()
                if not name:
                    continue

                store_id = _get_or_create_store(conn, row.get("Store", ""))

                # Check if item exists by barcode or name+brand
                barcode = row.get("Barcode", "").strip() or None
                brand = row.get("Brand", "").strip() or None
                existing = None
                if barcode:
                    existing = conn.execute(
                        "SELECT id FROM pantry WHERE barcode = ?", (barcode,)
                    ).fetchone()
                if not existing:
                    existing = conn.execute(
                        "SELECT id FROM pantry WHERE name = ? AND (brand = ? OR brand IS NULL)",
                        (name, brand),
                    ).fetchone()

                qty_str = row.get("Quantity", "1").strip()
                try:
                    quantity = float(qty_str) if qty_str else 1.0
                except ValueError:
                    quantity = 1.0

                fields = {
                    "barcode": barcode,
                    "category": row.get("Category", "").strip() or None,
                    "location": row.get("Location", "").strip() or None,
                    "brand": brand,
                    "name": name,
                    "quantity": quantity,
                    "unit": row.get("Unit", "").strip() or None,
                    "stocked_date": row.get("Stocked", "").strip() or None,
                    "best_by": row.get("Best By", "").strip() or None,
                    "preferred_store_id": store_id,
                    "product_notes": row.get("Product Notes", "").strip() or None,
                    "item_notes": row.get("Item Notes", "").strip() or None,
                }

                if existing:
                    conn.execute(
                        """UPDATE pantry SET barcode=:barcode, category=:category,
                           location=:location, brand=:brand, name=:name,
                           quantity=:quantity, unit=:unit, stocked_date=:stocked_date,
                           best_by=:best_by, preferred_store_id=:preferred_store_id,
                           product_notes=:product_notes, item_notes=:item_notes
                           WHERE id=:id""",
                        {**fields, "id": existing["id"]},
                    )
                    updated += 1
                else:
                    conn.execute(
                        """INSERT INTO pantry (barcode, category, location, brand, name,
                           quantity, unit, stocked_date, best_by, preferred_store_id,
                           product_notes, item_notes)
                           VALUES (:barcode, :category, :location, :brand, :name,
                           :quantity, :unit, :stocked_date, :best_by,
                           :preferred_store_id, :product_notes, :item_notes)""",
                        fields,
                    )
                    inserted += 1

            conn.commit()
        finally:
            conn.close()

    return inserted, updated


def get_all(location: Optional[str] = None, category: Optional[str] = None) -> list[PantryItem]:
    """Return all pantry items, optionally filtered by location and/or category."""
    conn = get_connection()
    try:
        query = "SELECT * FROM pantry WHERE 1=1"
        params = []
        if location:
            query += " AND location = ?"
            params.append(location)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY category, name"
        rows = conn.execute(query, params).fetchall()
        return [PantryItem(**dict(row)) for row in rows]
    finally:
        conn.close()


def get(item_id: int) -> Optional[PantryItem]:
    """Return a single pantry item by ID, or None if not found."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM pantry WHERE id = ?", (item_id,)).fetchone()
        return PantryItem(**dict(row)) if row else None
    finally:
        conn.close()


def add(item: PantryItem) -> int:
    """Insert a new pantry item and return its ID."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO pantry (barcode, category, location, brand, name,
               quantity, unit, stocked_date, best_by, preferred_store_id,
               product_notes, item_notes, estimated_price, is_staple)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                item.barcode, item.category, item.location, item.brand,
                item.name, item.quantity, item.unit, item.stocked_date,
                item.best_by, item.preferred_store_id, item.product_notes,
                item.item_notes, item.estimated_price, int(item.is_staple),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update(item: PantryItem) -> None:
    """Update an existing pantry item by its ID."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE pantry SET barcode=?, category=?, location=?, brand=?,
               name=?, quantity=?, unit=?, stocked_date=?, best_by=?,
               preferred_store_id=?, product_notes=?, item_notes=?,
               estimated_price=?, is_staple=?
               WHERE id=?""",
            (
                item.barcode, item.category, item.location, item.brand,
                item.name, item.quantity, item.unit, item.stocked_date,
                item.best_by, item.preferred_store_id, item.product_notes,
                item.item_notes, item.estimated_price, int(item.is_staple),
                item.id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def delete(item_id: int) -> None:
    """Delete a pantry item by ID."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM pantry WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()


def delete_many(item_ids: list[int]) -> int:
    """Delete multiple pantry items. Return count deleted."""
    if not item_ids:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in item_ids)
        cursor = conn.execute(f"DELETE FROM pantry WHERE id IN ({placeholders})", item_ids)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_expiring_soon(days: int = 7) -> list[PantryItem]:
    """Return pantry items whose best_by date falls within the next N days."""
    conn = get_connection()
    try:
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        today = date.today().isoformat()
        rows = conn.execute(
            "SELECT * FROM pantry WHERE best_by IS NOT NULL AND best_by <= ? AND best_by >= ? ORDER BY best_by",
            (cutoff, today),
        ).fetchall()
        return [PantryItem(**dict(row)) for row in rows]
    finally:
        conn.close()


def get_locations() -> list[str]:
    """Return distinct location values currently in the pantry."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT location FROM pantry WHERE location IS NOT NULL ORDER BY location"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def get_categories() -> list[str]:
    """Return distinct category values currently in the pantry."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM pantry WHERE category IS NOT NULL ORDER BY category"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def get_all_stores() -> list[Store]:
    """Return all stores sorted alphabetically by name."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM stores ORDER BY name").fetchall()
        return [Store(**dict(row)) for row in rows]
    finally:
        conn.close()
