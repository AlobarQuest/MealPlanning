# Staples UI Design

**Goal:** Expose the existing staples backend as a view within the Pantry tab.

**Date:** 2026-03-05

---

## Context

`meal_planner/core/staples.py` and the `staples` DB table are fully implemented. Staples are items the user always keeps on hand (salt, oil, butter) — independent of pantry inventory. When `need_to_buy = True`, the item is automatically added to shopping lists; when `False`, it is excluded. The web UI currently has no way to view or manage them.

---

## Architecture

No backend changes needed — the core module and DB schema are complete. This is purely a web layer addition: one new router, one new template, and a modification to the Pantry page.

---

## Components

### Toggle (Pantry page header)

A pill-style "Inventory / Staples" toggle sits at the top of the Pantry page, above the filter row. Clicking "Staples" fires an HTMX GET to `/pantry/staples` and swaps the main content area. Clicking "Inventory" fires an HTMX GET to `/pantry/rows` and restores the inventory table. The active pill is highlighted.

### Staples view (`partials/staples_list.html`)

A table with columns: checkbox, Name, Status ("On Hand" / "Needed").

Above the table: two action buttons — "Mark as Needed" and "Mark as On Hand". Both are disabled until at least one checkbox is selected (JS enables them on change). Both submit a form via HTMX POST with the selected IDs, then refresh the staples list partial.

Each row also has an Edit button (opens modal) and a Delete button (inline HTMX delete with confirmation).

### Add/Edit dialog (`partials/staple_dialog.html`)

Fields: Name only. An "Add Staple" button above the table opens this modal via HTMX. Edit reuses the same dialog pre-filled.

### Routes (new: `app/routers/staples.py`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pantry/staples` | Returns `partials/staples_list.html` |
| POST | `/pantry/staples/add` | Adds a staple, returns refreshed list |
| GET | `/pantry/staples/{id}/edit` | Returns pre-filled `staple_dialog.html` |
| POST | `/pantry/staples/{id}/edit` | Saves edit, returns refreshed list |
| POST | `/pantry/staples/{id}/delete` | Deletes, returns refreshed list |
| POST | `/pantry/staples/bulk-status` | Sets need_to_buy for a list of IDs, returns refreshed list |

### Demo mode

Staples view is visible in demo mode. Add, Edit, Delete, and bulk-status actions are hidden.

---

## Data Flow

1. User toggles to Staples → HTMX swaps content area with staples list
2. User checks rows → JS enables action buttons
3. User clicks "Mark as Needed" → POST `/pantry/staples/bulk-status` with `ids[]=…&need=1`
4. Server calls `staples.set_need_to_buy()` for each ID → returns refreshed partial
5. Shopping list generation already reads `staples` table — no changes needed there

---

## Testing

- Staples list renders (200)
- Add creates a staple
- Edit updates name
- Delete removes staple
- Bulk-status sets need_to_buy correctly for multiple IDs
- Demo mode: list renders, write routes return 405 or redirect
