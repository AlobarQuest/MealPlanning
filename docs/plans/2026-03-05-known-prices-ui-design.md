# Known Prices UI Design

**Goal:** Expose the existing known_prices backend as a "Price Book" section within the Stores tab, with manual entry and AI-powered receipt import.

**Date:** 2026-03-05

---

## Context

`meal_planner/core/known_prices.py` and the `known_prices` DB table are fully implemented. Known prices are item name → unit price → store mappings sourced from receipts or manual entry. The shopping list generator already reads this table to annotate items with prices. The web UI currently has no way to view or manage them.

---

## Architecture

One new router (`app/routers/known_prices.py`) added to the app. The Stores template gets a second section below the existing stores table. AI receipt parsing is a new `sync def` route that calls the Anthropic API.

---

## Components

### Stores page layout

The Stores tab gets two sections separated by a heading:
1. **Stores** — existing table (unchanged)
2. **Price Book** — new section below

### Price Book table (`partials/price_list.html`)

Columns: Item Name, Price, Unit, Store. A "Filter by store" dropdown above the table filters rows client-side (or via HTMX query param). Each row has a Delete button (HTMX inline delete, refreshes list).

### Add Price dialog (`partials/price_dialog.html`)

Fields: Item Name (text), Unit Price (number, step=0.01), Unit (text, optional), Store (dropdown of existing stores, optional). An "Add Price" button above the Price Book table opens this modal. On save, refreshes the price list partial.

### Import from Receipt dialog (`partials/price_import_dialog.html`)

A two-step modal:

**Step 1 — Paste receipt:**
- Store dropdown (required — applies to all extracted items)
- Textarea for pasting raw receipt text
- "Extract Prices" button → POST to `/stores/prices/import/parse`

**Step 2 — Review extracted prices:**
- Server returns a review table rendered in the same modal
- Each extracted row has: checkbox (checked by default), item name, price, unit
- "Save Selected" button → POST to `/stores/prices/import/save` with checked rows + store_id
- Server calls `known_prices.bulk_upsert()`, returns refreshed price list, closes modal

### AI extraction (`core/ai_assistant.py` addition)

New function `parse_receipt(text) -> list[dict]`:
- Sends receipt text to Claude with a prompt to extract grocery items and prices
- Returns list of `{item_name, unit_price, unit}` dicts
- Response format: JSON in code fence (consistent with existing AI functions)

### Routes (new: `app/routers/known_prices.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stores/prices` | Returns `partials/price_list.html` |
| GET | `/stores/prices/add` | Returns `partials/price_dialog.html` |
| POST | `/stores/prices/add` | Saves price, returns refreshed list |
| POST | `/stores/prices/{id}/delete` | Deletes, returns refreshed list |
| GET | `/stores/prices/import` | Returns `partials/price_import_dialog.html` (step 1) |
| POST | `/stores/prices/import/parse` | Calls AI, returns step 2 review table |
| POST | `/stores/prices/import/save` | Bulk upserts, returns refreshed list, closes modal |

### Demo mode

Price Book is visible in demo mode. Add, Delete, and import actions are hidden.

---

## Data Flow

**Manual add:**
User opens dialog → fills form → POST → `known_prices.upsert()` → refreshed list

**Receipt import:**
User pastes text + selects store → POST parse → Claude extracts prices → review table → user unchecks unwanted → POST save → `known_prices.bulk_upsert()` → refreshed price list

---

## Testing

- Price list renders (200)
- Add price saves and appears in list
- Delete removes price
- Import parse returns review table with extracted items
- Import save persists checked items, skips unchecked
- Demo mode: list renders, write routes blocked
