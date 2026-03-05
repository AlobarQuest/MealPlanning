# Starter Recipes Empty State Design

**Goal:** Show a prompt on the Recipes page when the library is empty, letting the user load 20 pre-built starter recipes with one click.

**Date:** 2026-03-05

---

## Context

`meal_planner/core/starter_recipes.py` contains 20 ready-to-use recipes (breakfast, lunch, dinner, snack) and a `seed_starter_recipes()` function that inserts them only if the `recipes` table is empty. This function is never called in the web app. New users land on the Recipes page to an empty list with no guidance.

---

## Architecture

Minimal change: one new route, a modified empty state in the recipe list partial, and a call to `seed_starter_recipes()` in the route handler.

---

## Components

### Empty state (`partials/recipe_list.html`)

The existing "No recipes found" text is replaced with a richer empty state when `q` (search query) is empty AND the list is empty:

```
Your recipe library is empty.
[Load starter recipes]
```

When a search query is active and returns no results, the original "No recipes found" message is shown instead (no button — seeding wouldn't help here).

The "Load starter recipes" button fires HTMX POST to `/recipes/seed`, targeting `#recipe-list`. No page reload.

### Seed route (`app/routers/recipes.py` addition)

`POST /recipes/seed`:
- Calls `seed_starter_recipes()` (idempotent — no-op if recipes exist)
- Returns `partials/recipe_list.html` with the full recipe list
- Not available in demo mode (demo DB is seeded separately via `demo/seed.py`)

### No settings or flags needed

`seed_starter_recipes()` already checks the table count before inserting. The empty state simply disappears once recipes exist — no persistent flag required.

---

## Data Flow

1. User visits `/recipes` with empty library
2. `recipe_list.html` renders the empty state with "Load starter recipes" button
3. User clicks → HTMX POST `/recipes/seed`
4. Server calls `seed_starter_recipes()` → 20 recipes inserted
5. Server returns updated `recipe_list.html` with all 20 recipes
6. List panel updates in place — user can immediately click any recipe

---

## Testing

- Empty state renders with button when recipe list is empty
- POST `/recipes/seed` inserts 20 recipes and returns populated list
- Calling seed twice is safe (idempotent)
- Search empty state ("No recipes found") does not show the seed button
- Demo mode: seed route not wired (demo DB handled separately)
