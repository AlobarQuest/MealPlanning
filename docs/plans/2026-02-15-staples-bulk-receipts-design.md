# Staples Redesign, Bulk Delete & Receipt Pricing — Design

**Date:** 2026-02-15

**Goal:** Four enhancements: (1) redesign staples as an independent persistent list with have/need toggles, (2) bulk delete in pantry, (3) receipt photo scanning for price extraction, (4) remove the now-obsolete `is_staple` pantry flag.

---

## Feature 1: Staples Redesign

### Problem
Staples are currently a flag on pantry items (`is_staple` column). When a pantry item is consumed or deleted, the staple knowledge is lost. Users need a persistent list of items they normally keep on hand, independent of current pantry inventory.

### Design

**New `staples` table:**
```sql
CREATE TABLE IF NOT EXISTS staples (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    name               TEXT NOT NULL UNIQUE,
    category           TEXT,
    preferred_store_id INTEGER REFERENCES stores(id),
    need_to_buy        INTEGER DEFAULT 0
);
```

**Key behaviors:**
- Staples are a standalone list, independent of pantry items.
- Each staple has a `need_to_buy` toggle (manual only — user flips it).
- Staples with `need_to_buy = True` appear on the shopping list, grouped by store.
- Staples with `need_to_buy = False` are excluded from the shopping list (same as current behavior, but now persistent).

**UI: Manage Staples Dialog (accessible from Pantry tab)**
- Opened via "Manage Staples" button on the Pantry tab toolbar.
- Table view: Name, Category, Store, Have It / Need It toggle.
- Add / Edit / Delete buttons.
- The "Have It / Need It" toggle is a checkbox or toggle button directly in the table row for quick flipping.

**UI: Mark as Staple from Recipe**
- In RecipeEditDialog, right-clicking an ingredient row shows "Mark as Staple" in context menu.
- A small dialog appears with the ingredient name pre-filled (using normalized shopping name if available, raw name otherwise). User can edit before saving.
- If a staple with that name already exists, show a message rather than creating a duplicate.

**Shopping list integration:**
- `shopping_list.generate()` adds all staples where `need_to_buy = True` to the shopping list.
- These appear in their assigned store group, or in a "Staples" group if no store is set.
- Staple items are listed separately from recipe-derived items (so users can distinguish "I need this for a recipe" from "I'm restocking a staple").

**Migration from old `is_staple`:**
- On `init_db()`, check if pantry items exist with `is_staple = 1`.
- For each, create a corresponding entry in the `staples` table (name, category, preferred_store_id).
- The `is_staple` column on pantry remains in the DB (SQLite can't drop columns easily) but is no longer read or written by any code.

---

## Feature 2: Bulk Delete in Pantry

### Design

**Checkbox column added to pantry table:**
- New column 0 (leftmost) with a checkbox per row.
- Existing columns shift right by one.
- A "Select All" checkbox in the header.

**"Delete Selected" button:**
- Added to the Pantry tab toolbar (next to existing Delete button).
- Disabled when no checkboxes are checked.
- On click: confirmation dialog showing count of selected items.
- On confirm: delete all selected items, refresh the table.

**Core function:**
```python
def delete_many(item_ids: list[int]) -> int:
    """Delete multiple pantry items. Return count deleted."""
```

---

## Feature 3: Receipt Photo → Price Extraction

### Design

**New `known_prices` table:**
```sql
CREATE TABLE IF NOT EXISTS known_prices (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name    TEXT NOT NULL UNIQUE,
    unit_price   REAL NOT NULL,
    unit         TEXT,
    store_id     INTEGER REFERENCES stores(id),
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Flow:**
1. "Scan Receipt" button on the Shopping tab toolbar.
2. File picker dialog → user selects one or more JPG/PNG photos.
3. Each image is sent to Claude's vision API with a prompt to extract line items: `(item_name, total_price, quantity)`. Unit price is calculated as `total_price / quantity`.
4. Results are shown in a review dialog: table with Item Name, Qty, Unit Price, Store columns. User can edit/remove rows and select the store (defaulting to the last used store).
5. On confirm: upsert into `known_prices` (update if item_name matches, insert otherwise).

**Price resolution in shopping list (priority order):**
1. `known_prices` table (receipt-sourced, most accurate)
2. `recipe_ingredients.estimated_price` (per-ingredient, manually set or AI-estimated)
3. `pantry.estimated_price` (pantry-sourced)
4. AI estimation (existing `estimate_prices()` function, least accurate)

**AI prompt for receipt parsing:**
- Uses Claude's vision capability (base64-encoded image).
- Prompt asks for JSON array: `[{"item": "...", "price": ..., "quantity": ...}]`
- Standard JSON-in-code-fences parsing pattern used throughout the app.

**Multiple images:** If the receipt is long and spans multiple photos, all images are sent in a single API call as multiple image content blocks.

---

## Summary of Changes

| Area | Change |
|------|--------|
| DB | New `staples` table, new `known_prices` table, migration from `is_staple` |
| Models | New `Staple` and `KnownPrice` dataclasses |
| Core | New `core/staples.py` module, `core/pantry.py` bulk delete, receipt parsing in `core/ai_assistant.py`, price resolution update in `core/shopping_list.py` |
| GUI | Manage Staples dialog, bulk delete checkbox column + button in pantry, "Mark as Staple" in recipe dialog, "Scan Receipt" in shopping tab with review dialog |
