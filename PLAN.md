# Meal Planning Application — Full Plan

## Overview

A cross-platform desktop application for managing food inventory, planning meals, generating shopping lists, and leveraging AI (Claude) for recipe management. Data is stored locally in SQLite. No web server required.

---

## Tech Stack

| Component | Technology | Reason |
|---|---|---|
| GUI Framework | PySide6 (Qt6) | Polished cross-platform widgets, tables, forms |
| Database | SQLite (via Python `sqlite3`) | Embedded, single-file, no server needed |
| AI Integration | Anthropic SDK (Claude) | Recipe parsing, generation, meal suggestions |
| HTTP Client | httpx | Fetching recipe URLs |
| Language | Python 3.10+ | Widely available, easy to maintain |

---

## Project Structure

```
meal_planner/
├── main.py                  # Entry point — launches the Qt application
├── config.py                # App-wide settings (API key, DB path, preferences)
├── requirements.txt
├── db/
│   ├── __init__.py
│   ├── database.py          # Connection management, schema creation, migrations
│   └── models.py            # Dataclass definitions for all entities
├── core/
│   ├── __init__.py
│   ├── pantry.py            # Pantry CRUD + CSV import logic
│   ├── recipes.py           # Recipe CRUD
│   ├── meal_plan.py         # Meal plan CRUD + week navigation helpers
│   ├── shopping_list.py     # Shopping list generation (needs - pantry = buy)
│   └── ai_assistant.py      # All Claude API calls (parse, generate, suggest)
└── gui/
    ├── __init__.py
    ├── main_window.py       # QMainWindow with tab bar and global actions
    ├── pantry_tab.py        # Pantry inventory management UI
    ├── recipes_tab.py       # Recipe browser, editor, AI import UI
    ├── meal_plan_tab.py     # Weekly calendar grid UI
    └── shopping_tab.py      # Shopping list generation and export UI
```

---

## Database Schema

### `stores`
Stores/shops where ingredients are purchased.
```sql
CREATE TABLE stores (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
```

### `pantry`
Current inventory, imported from PantryChecker CSV or managed manually.
```sql
CREATE TABLE pantry (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode          TEXT,
    category         TEXT,
    location         TEXT,          -- 'Pantry', 'Fridge', 'Freezer'
    brand            TEXT,
    name             TEXT NOT NULL,
    quantity         REAL DEFAULT 1,
    unit             TEXT,
    stocked_date     TEXT,          -- ISO date YYYY-MM-DD
    best_by          TEXT,          -- ISO date YYYY-MM-DD
    preferred_store_id INTEGER REFERENCES stores(id),
    product_notes    TEXT,
    item_notes       TEXT
);
```

### `recipes`
Stored recipes (manually entered, AI-generated, or URL-imported).
```sql
CREATE TABLE recipes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    description  TEXT,
    servings     INTEGER DEFAULT 4,
    prep_time    TEXT,
    cook_time    TEXT,
    instructions TEXT,
    source_url   TEXT,
    tags         TEXT,              -- comma-separated (e.g. "chicken,quick,dinner")
    created_at   TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### `recipe_ingredients`
Ingredients for each recipe, linked by recipe_id.
```sql
CREATE TABLE recipe_ingredients (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    quantity  REAL,
    unit      TEXT
);
```

### `meal_plan`
Maps a date + meal slot to a recipe with a serving count.
```sql
CREATE TABLE meal_plan (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date      TEXT NOT NULL,        -- ISO date YYYY-MM-DD
    meal_slot TEXT NOT NULL,        -- 'Breakfast', 'Lunch', 'Dinner', 'Snack'
    recipe_id INTEGER REFERENCES recipes(id) ON DELETE SET NULL,
    servings  INTEGER DEFAULT 1,
    notes     TEXT
);
```

### `settings`
Key-value store for user preferences.
```sql
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
```

---

## CSV Import Mapping (PantryChecker Format)

| CSV Column | DB Column | Notes |
|---|---|---|
| Barcode | barcode | Stored as-is |
| Category | category | |
| Location | location | Pantry / Fridge / Freezer |
| Brand | brand | |
| Name | name | |
| Quantity | quantity | Parsed as float |
| Stocked | stocked_date | Parsed to ISO date |
| Best By | best_by | Parsed to ISO date |
| Store | preferred_store_id | Resolved/created in stores table |
| Product Notes | product_notes | |
| Item Notes | item_notes | |

Columns not imported: Barcode type prefix, Best By Source, Total Price, Unit Price, Price Source, Store Address.

---

## Core Logic

### Pantry (`core/pantry.py`)
- `import_csv(filepath)` — Parse PantryChecker CSV, upsert rows by barcode+name
- `get_all(location=None, category=None)` — Filtered list
- `add(item)`, `update(item)`, `delete(id)`
- `get_expiring_soon(days=7)` — Items expiring within N days

### Recipes (`core/recipes.py`)
- `get_all()`, `get(id)`, `search(query)`
- `add(recipe, ingredients)`, `update(recipe, ingredients)`, `delete(id)`

### Meal Plan (`core/meal_plan.py`)
- `get_week(start_date)` — Returns all meal_plan rows for Mon–Sun of given week
- `set_meal(date, slot, recipe_id, servings)`
- `clear_meal(date, slot)`
- `get_week_start(date)` — Returns Monday of the week containing date

### Shopping List (`core/shopping_list.py`)
- `generate(start_date, end_date)` — Aggregates all recipe_ingredients for planned meals in range, subtracts pantry quantities, groups by preferred store
- Returns: `{store_name: [(ingredient, qty_needed, unit), ...]}`

### AI Assistant (`core/ai_assistant.py`)
All methods call Claude API with relevant context.

| Method | Input | Output |
|---|---|---|
| `parse_recipe_text(text)` | Raw pasted recipe text | Structured Recipe + ingredients |
| `parse_recipe_url(url)` | URL string | Fetches HTML, Claude extracts recipe |
| `generate_recipe(pantry_items, preferences)` | Pantry list + optional prompt | New Recipe + ingredients |
| `suggest_week(pantry, existing_recipes, preferences)` | Context | List of 7-day meal suggestions |
| `modify_recipe(recipe, instruction)` | Recipe + change request | Modified Recipe |

---

## GUI Layout

### Main Window
- Title bar: "Meal Planner"
- Tab bar: Pantry | Recipes | Meal Plan | Shopping List
- Menu bar: File (Import CSV, Export, Settings, Quit) | Help

### Pantry Tab
- Toolbar: [Import CSV] [Add Item] [Edit] [Delete] [Filter dropdown]
- Table view: Name | Brand | Category | Location | Qty | Best By | Store
- Row color coding: red = expired, orange = expiring within 7 days
- Double-click row to edit

### Recipes Tab
- Left panel: Scrollable recipe list with search bar
- Right panel: Recipe detail view
  - Name, description, tags, servings, prep/cook time
  - Ingredients list
  - Instructions text
  - Source URL (clickable)
- Toolbar: [Add Manual] [Paste Text] [Import URL] [AI Generate] [Edit] [Delete]

### Meal Plan Tab
- Week navigator: [← Prev] "Week of MMM DD" [Next →] [Today]
- Grid: 7 columns (Mon–Sun) × 4 rows (Breakfast/Lunch/Dinner/Snack)
- Each cell shows recipe name (or empty)
- Click cell → picker dialog to select/clear recipe
- Button: [AI Suggest Week]

### Shopping List Tab
- Week selector (defaults to current week)
- [Generate List] button
- Output: grouped by store, each group is a checklist
- [Export to Text] [Copy to Clipboard] buttons

---

## AI Integration Details

### API Key Storage
- Stored in the `settings` table under key `claude_api_key`
- Input via Settings dialog (File → Settings)
- Never written to any file outside the DB

### Prompt Strategy
- Every AI call includes current pantry contents as context
- Responses requested in JSON format for reliable parsing
- Fallback: if JSON parse fails, show raw AI response for manual use

### Recipe Parsing Flow (URL)
1. httpx fetches the URL HTML
2. HTML is stripped to readable text (remove scripts/styles)
3. Claude is sent the text with instructions to extract: name, description, servings, prep_time, cook_time, ingredients (name/qty/unit), instructions
4. Response parsed into Recipe + RecipeIngredient objects
5. User shown preview dialog before saving

### Recipe Parsing Flow (Paste)
1. User pastes text into dialog
2. Same Claude extraction as above
3. Preview + confirm before saving

---

## Data Flow Summary

```
PantryChecker CSV
       ↓
  Import CSV → pantry table
       ↓
  Plan meals → meal_plan table (references recipes)
       ↓
  Generate shopping list → (meal ingredients × servings) - pantry stock
       ↓
  Export grouped by store
```

---

## Setup & Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

On first run, the SQLite database is created automatically at `~/.meal_planner/meal_planner.db`.

---

## Future Enhancements (out of scope for v1)

- Nutritional information tracking
- Recipe rating/favorites
- Meal plan templates (save/load a week)
- Auto-sync back to PantryChecker (if API available)
- Print-friendly shopping list
- Recipe image support
- Barcode scanning for manual pantry additions
