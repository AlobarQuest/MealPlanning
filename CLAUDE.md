# Meal Planner — System Reference

Developer and AI reference for the Meal Planner codebase.
See also: `README.md` (user guide) and `PLAN.md` (original design spec).

---

## Project Overview

A web application for managing food inventory, planning weekly meals, generating shopping lists, and leveraging Claude AI for recipe management. All data lives in a local SQLite database. Runs locally or in Docker; accessible from any browser on the network.

| Component        | Technology                          |
|------------------|-------------------------------------|
| Web framework    | FastAPI 0.115+ + Uvicorn            |
| Templates        | Jinja2 + HTMX 2.x                  |
| Database         | SQLite via `sqlite3`                |
| AI               | Anthropic SDK (Claude)              |
| HTTP             | httpx                               |
| Language         | Python 3.10+                        |

### Running

**Local development:**
```bash
cp .env.example .env   # fill in APP_PASSWORD, SECRET_KEY, CLAUDE_API_KEY
uvicorn app.main:app --reload --port 8080
```

**Docker:**
```bash
APP_PASSWORD=mypass SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") docker compose up --build
```

Database is auto-created on first run. Default path: `~/.meal_planner/meal_planner.db` (or `DB_PATH` env var).

Demo mode (no login required): `http://localhost:8080/demo/pantry`

---

## Architecture

Three layers with strict top-down dependencies:

```
┌──────────────────────────────────────────────────┐
│  Web Layer  (app/)                               │
│  FastAPI routers + Jinja2 templates + HTMX       │
│  Calls core modules; never touches DB directly   │
└──────────────────┬───────────────────────────────┘
                   │ calls
┌──────────────────▼───────────────────────────────┐
│  Core Layer  (meal_planner/core/)                │
│  Business logic — CRUD, CSV import, AI calls     │
│  Each module owns one domain area                │
└──────────────────┬───────────────────────────────┘
                   │ calls
┌──────────────────▼───────────────────────────────┐
│  DB Layer  (meal_planner/db/)                    │
│  Connection management, schema, dataclass models │
└──────────────────────────────────────────────────┘
```

### Module Dependency Map

```
app/main.py  (FastAPI app, auth middleware, lifespan)
  ├── db.database.init_db()
  ├── demo.seed.seed_if_empty()
  └── app/routers/*

app/routers/auth.py      → templates, dependencies
app/routers/pantry.py    → core.pantry, db.models
app/routers/recipes.py   → core.recipes, core.ai_assistant, db.models
app/routers/meal_plan.py → core.meal_plan, core.recipes, core.ai_assistant
app/routers/shopping.py  → core.shopping_list, core.meal_plan
app/routers/stores.py    → core.stores, db.models
app/routers/settings.py  → config
app/routers/demo.py      → all core modules (with override_db_path)

core/pantry.py           → db.database, db.models
core/recipes.py          → db.database, db.models
core/meal_plan.py        → db.database, db.models
core/shopping_list.py    → db.database, core.meal_plan
core/ai_assistant.py     → db.database, db.models, anthropic, httpx
config.py                → db.database
```

---

## Database

### Connection Conventions

- **Fresh connection per call**: every function calls `get_connection()`, uses it, and closes it in a `finally` block.
- **Row factory**: all connections use `sqlite3.Row` so rows can be accessed by column name.
- **Foreign keys**: enforced via `PRAGMA foreign_keys = ON` on every connection.
- **No migration system**: `init_db()` uses `CREATE TABLE IF NOT EXISTS`.

### Schema Summary

| Table                | Purpose                                      | Key Relationships                        |
|----------------------|----------------------------------------------|------------------------------------------|
| `stores`             | Store/shop names                             | Referenced by `pantry.preferred_store_id` |
| `pantry`             | Inventory items (from CSV or manual)         | FK → `stores(id)`                        |
| `recipes`            | Recipe library                               | —                                        |
| `recipe_ingredients` | Ingredients per recipe                       | FK → `recipes(id)` ON DELETE CASCADE     |
| `meal_plan`          | Date + slot → recipe assignments             | FK → `recipes(id)` ON DELETE SET NULL    |
| `settings`           | Key-value config store                       | —                                        |

Full CREATE TABLE statements are in `db/database.py:init_db()` and documented in `PLAN.md`.

### Settings Keys

| Key              | Value                              | Used By                    |
|------------------|------------------------------------|----------------------------|
| `claude_api_key` | Anthropic API key (`sk-ant-...`)   | `core/ai_assistant.py`     |

---

## Core Modules

### `config.py` — Settings Management

```python
get_setting(key, default=None) -> str      # Read a setting
set_setting(key, value) -> None            # Upsert a setting
```

### `core/pantry.py` — Pantry Inventory

```python
import_csv(filepath) -> (inserted, updated)        # PantryChecker CSV import
get_all(location=None, category=None) -> [PantryItem]  # Filtered list
get(item_id) -> PantryItem | None                  # Single item by ID
add(item) -> int                                   # Insert, return ID
update(item) -> None                               # Update by ID
delete(item_id) -> None                            # Delete by ID
get_expiring_soon(days=7) -> [PantryItem]          # Expiring within N days
get_locations() -> [str]                           # Distinct locations
get_categories() -> [str]                          # Distinct categories
get_all_stores() -> [Store]                        # All stores, sorted
```

**CSV import logic**: matches existing items by barcode first, then by name+brand. Unmatched items are inserted. Store names are auto-created.

### `core/recipes.py` — Recipe Library

```python
get_all() -> [Recipe]                    # All recipes, sorted by name
get(recipe_id) -> Recipe | None          # Single recipe with ingredients
search(query) -> [Recipe]                # Search name/description/tags (LIKE)
add(recipe) -> int                       # Insert recipe + ingredients
update(recipe) -> None                   # Update recipe; delete-and-replace ingredients
delete(recipe_id) -> None                # Delete (ingredients cascade)
```

### `core/meal_plan.py` — Meal Planning

```python
MEAL_SLOTS = ["Breakfast", "Lunch", "Dinner", "Snack"]

get_week_start(for_date=None) -> date              # Monday of containing week
get_week(start_date) -> {date_str: {slot: MealPlanEntry}}  # Full week grid
set_meal(date, slot, recipe_id, servings=1, notes=None)    # Insert/update/delete
clear_meal(date, slot) -> None                     # Remove assignment
get_meals_in_range(start, end) -> [MealPlanEntry]  # Date range query
```

### `core/shopping_list.py` — Shopping List Generation

```python
generate(start_date, end_date, use_pantry=True) -> {store: [(name, qty, unit)]}
format_shopping_list(shopping_list) -> str          # Plain-text export with checkboxes
```

**Generation algorithm**:
1. Fetch all meal plan entries in the date range.
2. For each recipe, load ingredients and multiply quantities by servings.
3. Aggregate by `(ingredient_name_lower, unit)`.
4. If `use_pantry=True`: subtract pantry stock; skip items with sufficient stock.
5. Look up preferred store from pantry table for each item.
6. Group by store, sort alphabetically within each store.

**Ingredient matching**: case-insensitive, whitespace-trimmed (`.lower().strip()`).

### `core/ai_assistant.py` — Claude AI Integration

```python
parse_recipe_text(text) -> Recipe | None           # Parse pasted recipe text
parse_recipe_url(url) -> Recipe | None             # Fetch URL, extract recipe
generate_recipe(preferences="") -> Recipe | None   # Generate from pantry
suggest_week(recipe_names, preferences="") -> [dict]  # Week of meal suggestions
modify_recipe(recipe, instruction) -> Recipe | None   # Modify existing recipe
```

**API details**:
- Model: `claude-opus-4-5-20251101`
- Max tokens: 2048 per call
- API key: read from `settings` table (`claude_api_key`)
- Response format: JSON in code fences, parsed with regex + `json.loads`
- Pantry context: included in generate and suggest prompts via `_get_pantry_summary()`
- URL import: HTML stripped to text, truncated to 12,000 chars

---

## Web Layer (app/)

### Tab Structure

| URL prefix      | Router file                  | Template                          |
|-----------------|------------------------------|-----------------------------------|
| `/pantry`       | `app/routers/pantry.py`      | `app/templates/pantry.html`       |
| `/recipes`      | `app/routers/recipes.py`     | `app/templates/recipes.html`      |
| `/meal-plan`    | `app/routers/meal_plan.py`   | `app/templates/meal_plan.html`    |
| `/shopping`     | `app/routers/shopping.py`    | `app/templates/shopping.html`     |
| `/stores`       | `app/routers/stores.py`      | `app/templates/stores.html`       |
| `/settings`     | `app/routers/settings.py`    | `app/templates/settings.html`     |
| `/demo/*`       | `app/routers/demo.py`        | (reuses all templates, demo=True) |
| `/login`, `/logout` | `app/routers/auth.py`    | `app/templates/login.html`        |

### Key Web Patterns

**HTMX partial swaps**: most interactive actions swap only part of the page. Partials live in `app/templates/partials/`.

**Auth**: single-password session via signed cookie (`itsdangerous`). Middleware redirects unauthenticated requests to `/login`. `/demo/*` and `/static/*` are public.

**Dialog pattern**: HTMX loads partials into `#modal-container`; JS opens the `<dialog>` element. Close button or backdrop click removes it.

**AI operations**: `sync def` routes (FastAPI runs in thread pool) for blocking Anthropic API calls. AI result populates a pre-filled `recipe_dialog.html` for user review before saving.

**Demo mode**: `app/routers/demo.py` uses `override_db_path()` context manager to point all core/ calls at the demo DB. Templates detect `demo=True` to hide write buttons.

### Pantry Tab

- Filterable table (location + category combos trigger HTMX row reload).
- Color coding: expired → red; expiring within 7 days → orange.
- CSV import via HTMX file upload.

### Recipes Tab

- Split-pane: search list (left) + detail panel (right), both HTMX-driven.
- Dynamic ingredient rows in add/edit dialog (HTMX append + JS renumber).
- AI operations: Paste Text, From URL, AI Generate, Modify with AI.

### Meal Plan Tab

- HTMX week navigation (Prev/Next/Today buttons swap `#meal-grid`).
- 4×7 grid (slots × days); clicking a cell opens the meal picker dialog.
- AI suggest week: shows proposed meals in a review table before applying.

### Shopping Tab

- Date range pickers + "This Week" JS shortcut.
- "Subtract pantry items" checkbox.
- HTMX generate → grouped checkboxes by store.
- Export as plain text download.

---

## Data Flow

```
PantryChecker CSV → File → Import Pantry CSV → pantry table
                                                     ↓
User adds recipes (manual / paste / URL / AI) → recipes table
                                                     ↓
User assigns recipes to dates+slots → meal_plan table
                                                     ↓
Generate shopping list → aggregate ingredients × servings
                       → subtract pantry stock (optional)
                       → group by preferred store
                       → display in tree / copy to clipboard
```

---

## Key Patterns & Conventions

1. **Connection lifecycle**: open → use → close in `finally`. Never reuse connections across calls.
2. **Dataclass models**: plain `@dataclass` containers in `db/models.py`. No ORM.
3. **Ingredient name matching**: always `name.lower().strip()` for comparisons.
4. **CSV upsert**: match by barcode first, then by name+brand. Auto-create stores.
5. **AI response parsing**: expect JSON in ````json` code fences, fallback to raw text.
6. **Jinja2 loop indexing**: use `loop.index0` (not Python's `enumerate`) inside `{% for %}` blocks.
7. **Tests**: `pytest tests/` — uses in-memory SQLite via `DB_PATH` env var. 49 tests across auth, pantry, stores, recipes, meal plan, shopping, and demo.
