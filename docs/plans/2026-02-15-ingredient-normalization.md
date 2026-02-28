# Ingredient Normalization & Staples Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve shopping list accuracy by (1) letting users mark pantry items as "staples" that never appear on shopping lists, and (2) normalizing recipe ingredients into purchasable form using AI at recipe save time.

**Architecture:** Two independent features that both feed into shopping list generation. Staples adds a boolean flag to pantry items. Normalization adds three new fields (`shopping_name`, `shopping_qty`, `shopping_unit`) to recipe ingredients, populated by a new AI function at save time. Shopping list generation uses normalized fields when available, falls back to raw fields.

**Tech Stack:** Python 3.10+, SQLite, PySide6, Anthropic SDK (Claude API)

---

### Task 1: Add `is_staple` column to database and model

**Files:**
- Modify: `meal_planner/db/database.py:113-123` (migration block)
- Modify: `meal_planner/db/models.py:24-35` (PantryItem dataclass)

**Step 1: Add migration for `is_staple` column**

In `meal_planner/db/database.py`, add to the migration loop at line 113:

```python
for col, table, col_type in [
    ("location", "stores", "TEXT"),
    ("notes", "stores", "TEXT"),
    ("estimated_price", "pantry", "REAL"),
    ("estimated_price", "recipe_ingredients", "REAL"),
    ("is_staple", "pantry", "INTEGER DEFAULT 0"),
]:
```

**Step 2: Add `is_staple` field to PantryItem dataclass**

In `meal_planner/db/models.py`, add after the `estimated_price` field in `PantryItem`:

```python
is_staple: bool = False
```

**Step 3: Verify the app starts without error**

Run: `python main.py` — confirm it launches, then close it.

**Step 4: Commit**

```bash
git add meal_planner/db/database.py meal_planner/db/models.py
git commit -m "feat: add is_staple column to pantry table"
```

---

### Task 2: Wire `is_staple` through pantry CRUD and GUI

**Files:**
- Modify: `meal_planner/core/pantry.py:139-180` (add/update functions)
- Modify: `meal_planner/gui/pantry_tab.py:25-167` (PantryItemDialog)

**Step 1: Update `pantry.add()` to include `is_staple`**

In `meal_planner/core/pantry.py`, modify the `add()` function (line 139). Add `is_staple` to both the SQL and the parameters tuple:

```python
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
```

**Step 2: Update `pantry.update()` to include `is_staple`**

In `meal_planner/core/pantry.py`, modify the `update()` function (line 161):

```python
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
```

**Step 3: Add "Staple" checkbox to PantryItemDialog**

In `meal_planner/gui/pantry_tab.py`, in `PantryItemDialog.__init__()`:

After the `price_spin` setup (around line 67), add:

```python
self.staple_check = QCheckBox("Always on hand (exclude from shopping lists)")
```

After the `form.addRow("Est. Price/Unit:", self.price_spin)` line (line 77), add:

```python
form.addRow("Staple:", self.staple_check)
```

**Step 4: Populate the checkbox in `_populate()`**

In `_populate()` (line 89), add after the store lookup block (after line 114):

```python
self.staple_check.setChecked(bool(item.is_staple))
```

**Step 5: Read the checkbox in `get_item()`**

In `get_item()` (line 123), add `is_staple` to the returned `PantryItem`. Before the `return PantryItem(...)` statement, add:

```python
is_staple = self.staple_check.isChecked()
```

Then include `is_staple=is_staple` in the PantryItem constructor.

**Step 6: Handle `is_staple` type conversion in `get_all()` and `get()`**

The `PantryItem(**dict(row))` pattern in `get_all()` and `get()` will pass the integer from SQLite directly. Since Python treats `0`/`1` as falsy/truthy and the dataclass type is `bool`, this works automatically. However, `SELECT *` will now include `is_staple`. Verify this works by launching the app and opening the pantry tab.

**Step 7: Test manually**

Run: `python main.py` — Add a new pantry item with "Staple" checked. Edit it and verify the checkbox is still checked. Verify unchecking and saving works.

**Step 8: Commit**

```bash
git add meal_planner/core/pantry.py meal_planner/gui/pantry_tab.py
git commit -m "feat: add staple checkbox to pantry item CRUD and dialog"
```

---

### Task 3: Exclude staples from shopping list generation

**Files:**
- Modify: `meal_planner/core/shopping_list.py:58-78` (pantry lookup in `generate()`)

**Step 1: Modify the pantry query to include `is_staple`**

In `meal_planner/core/shopping_list.py`, change the pantry query at line 61-63:

```python
pantry_rows = conn.execute(
    "SELECT name, quantity, estimated_price, is_staple FROM pantry"
).fetchall()
```

**Step 2: Build a set of staple ingredient names**

After building `pantry_qty` (line 64), add:

```python
staple_names = {
    row["name"].lower().strip()
    for row in pantry_rows
    if row["is_staple"]
}
```

**Step 3: Skip staples in the buy loop**

In the loop at line 73, add a staple check right after the `for` line:

```python
for (ing_name, unit), needed in required.items():
    # Skip staple items — user always has these on hand
    if ing_name in staple_names:
        continue

    if use_pantry:
        # ... existing code
```

**Step 4: Test manually**

Run: `python main.py`
1. Mark "salt" and "black pepper" as staples in the pantry
2. Plan a meal that uses salt/pepper
3. Generate shopping list — verify salt/pepper do NOT appear
4. Uncheck "Subtract pantry items" — verify salt/pepper still do NOT appear (staples are always excluded regardless of the pantry toggle)

**Step 5: Commit**

```bash
git add meal_planner/core/shopping_list.py
git commit -m "feat: exclude staple items from shopping list generation"
```

---

### Task 4: Add normalized shopping fields to recipe_ingredients

**Files:**
- Modify: `meal_planner/db/database.py:113-123` (migration block)
- Modify: `meal_planner/db/models.py:38-47` (RecipeIngredient dataclass)

**Step 1: Add migrations for the three new columns**

In `meal_planner/db/database.py`, add to the migration loop:

```python
for col, table, col_type in [
    ("location", "stores", "TEXT"),
    ("notes", "stores", "TEXT"),
    ("estimated_price", "pantry", "REAL"),
    ("estimated_price", "recipe_ingredients", "REAL"),
    ("is_staple", "pantry", "INTEGER DEFAULT 0"),
    ("shopping_name", "recipe_ingredients", "TEXT"),
    ("shopping_qty", "recipe_ingredients", "REAL"),
    ("shopping_unit", "recipe_ingredients", "TEXT"),
]:
```

**Step 2: Add fields to RecipeIngredient dataclass**

In `meal_planner/db/models.py`, add after `estimated_price` in `RecipeIngredient`:

```python
shopping_name: Optional[str] = None
shopping_qty: Optional[float] = None
shopping_unit: Optional[str] = None
```

**Step 3: Verify app starts**

Run: `python main.py` — confirm launch, then close.

**Step 4: Commit**

```bash
git add meal_planner/db/database.py meal_planner/db/models.py
git commit -m "feat: add shopping normalization columns to recipe_ingredients"
```

---

### Task 5: Create AI normalization function

**Files:**
- Modify: `meal_planner/core/ai_assistant.py` (add `normalize_ingredients()` function)

**Step 1: Add `normalize_ingredients()` function**

Add this function after the `estimate_prices()` function (after line 336) in `meal_planner/core/ai_assistant.py`:

```python
def normalize_ingredients(ingredients: list[RecipeIngredient]) -> list[dict]:
    """Normalize recipe ingredients into purchasable shopping form.

    Takes a list of RecipeIngredient and returns a list of dicts:
    [{"shopping_name": str, "shopping_qty": float|None, "shopping_unit": str|None}, ...]

    The AI strips preparation instructions (drained, minced, divided, room temperature),
    converts recipe amounts to purchase units (30oz -> 2 cans), and preserves qualifiers
    that affect what to buy (canned, dry, fresh, frozen).
    """
    if not ingredients:
        return []

    client = _get_client()

    ing_lines = []
    for i, ing in enumerate(ingredients):
        qty_str = f"{ing.quantity:g}" if ing.quantity else "?"
        unit_str = ing.unit or ""
        ing_lines.append(f'{i}. {qty_str} {unit_str} {ing.name}'.strip())

    ingredients_text = "\n".join(ing_lines)

    prompt = f"""Convert these recipe ingredients into their purchasable shopping form.

For each ingredient:
1. Strip preparation instructions (drained, minced, divided, chopped, room temperature, etc.)
2. Convert to how the item is purchased (e.g. "30oz black beans drained" -> "canned black beans", qty 2, unit "15oz cans")
3. Keep qualifiers that affect what you buy: canned, dry, fresh, frozen, whole, ground, etc.
4. Use common grocery units: lbs, oz, each, bunch, cans, bags, bottles, etc.
5. Normalize the name to a common grocery name (e.g. "garlic cloves" -> "garlic")

Recipe ingredients:
{ingredients_text}

Return a JSON array with one entry per ingredient (same order), matching this schema:
```json
[
  {{"index": 0, "shopping_name": "chicken breast", "shopping_qty": 2, "shopping_unit": "lbs"}},
  {{"index": 1, "shopping_name": "garlic", "shopping_qty": 1, "shopping_unit": "head"}}
]
```

Return only the JSON array, wrapped in ```json``` code fences."""

    message = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    # Build result list aligned to input order
    result = []
    data_by_index = {item.get("index", i): item for i, item in enumerate(data)}
    for i in range(len(ingredients)):
        item = data_by_index.get(i, {})
        result.append({
            "shopping_name": item.get("shopping_name"),
            "shopping_qty": item.get("shopping_qty"),
            "shopping_unit": item.get("shopping_unit"),
        })

    return result
```

**Step 2: Verify import works**

Run: `python -c "from meal_planner.core.ai_assistant import normalize_ingredients; print('OK')"` — should print OK.

**Step 3: Commit**

```bash
git add meal_planner/core/ai_assistant.py
git commit -m "feat: add AI normalize_ingredients function"
```

---

### Task 6: Wire normalization into recipe save flow

**Files:**
- Modify: `meal_planner/core/recipes.py:80-128` (add/update functions)
- Modify: `meal_planner/gui/recipes_tab.py:921-941` (`_ai_recipe_received`)

**Step 1: Update `recipes.add()` to persist normalized fields**

In `meal_planner/core/recipes.py`, update the ingredient INSERT in `add()` (around line 96):

```python
for ing in recipe.ingredients:
    conn.execute(
        """INSERT INTO recipe_ingredients
           (recipe_id, name, quantity, unit, estimated_price,
            shopping_name, shopping_qty, shopping_unit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (recipe_id, ing.name, ing.quantity, ing.unit, ing.estimated_price,
         ing.shopping_name, ing.shopping_qty, ing.shopping_unit),
    )
```

**Step 2: Update `recipes.update()` to persist normalized fields**

In `meal_planner/core/recipes.py`, update the ingredient INSERT in `update()` (around line 124):

```python
for ing in recipe.ingredients:
    conn.execute(
        """INSERT INTO recipe_ingredients
           (recipe_id, name, quantity, unit, estimated_price,
            shopping_name, shopping_qty, shopping_unit)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (recipe.id, ing.name, ing.quantity, ing.unit, ing.estimated_price,
         ing.shopping_name, ing.shopping_qty, ing.shopping_unit),
    )
```

**Step 3: Update `recipes.get()` to load normalized fields**

In `meal_planner/core/recipes.py`, the `get()` function loads ingredients with `SELECT *`. Since `RecipeIngredient(**dict(row))` is used and we added the fields to the dataclass, this should work automatically. Verify by checking the `get()` function constructs ingredients via `RecipeIngredient(**dict(row))`.

**Step 4: Add "Normalize for Shopping" button to RecipeEditDialog**

In `meal_planner/gui/recipes_tab.py`, in the `RecipeEditDialog` class, add a button that triggers normalization. This button should:
- Collect current ingredients from the table
- Call `normalize_ingredients()` via an AIWorker
- On success, update the `RecipeIngredient` objects' `shopping_name`, `shopping_qty`, `shopping_unit` fields
- Show a brief confirmation message

The normalization results are stored on the ingredient objects but NOT shown in the edit table (they're behind-the-scenes data for shopping list generation). The user sees "Ingredients normalized for shopping" confirmation.

Find the button layout in RecipeEditDialog (where Save/Cancel buttons are) and add:

```python
self.normalize_btn = QPushButton("Normalize for Shopping")
self.normalize_btn.setToolTip("Use AI to convert ingredients to purchasable shopping form")
self.normalize_btn.clicked.connect(self._normalize_ingredients)
```

Add the handler method to RecipeEditDialog:

```python
def _normalize_ingredients(self):
    """Run AI normalization on current ingredients."""
    from meal_planner.core import ai_assistant
    ingredients = self._get_ingredients_from_table()
    if not ingredients:
        return
    self.normalize_btn.setEnabled(False)
    self.normalize_btn.setText("Normalizing...")

    def do_normalize():
        return ai_assistant.normalize_ingredients(ingredients)

    self._norm_worker = AIWorker(do_normalize)
    self._norm_worker.finished.connect(self._normalization_done)
    self._norm_worker.error.connect(self._normalization_error)
    self._norm_worker.start()

def _normalization_done(self, results):
    """Apply normalization results to ingredient objects."""
    self.normalize_btn.setEnabled(True)
    self.normalize_btn.setText("Normalize for Shopping")
    if not results:
        return
    # Store results — they'll be included when get_recipe() is called
    self._normalized_data = results
    QMessageBox.information(self, "Done",
        f"Normalized {len(results)} ingredients for shopping list.")

def _normalization_error(self, msg):
    self.normalize_btn.setEnabled(True)
    self.normalize_btn.setText("Normalize for Shopping")
    QMessageBox.warning(self, "Normalization Error", msg)
```

**Step 5: Update `get_recipe()` to include normalized data**

In RecipeEditDialog's `get_recipe()` method, after building the ingredients list, apply any stored normalization data:

```python
# Apply normalization data if available
if hasattr(self, '_normalized_data') and self._normalized_data:
    for i, ing in enumerate(ingredients):
        if i < len(self._normalized_data):
            norm = self._normalized_data[i]
            ing.shopping_name = norm.get("shopping_name")
            ing.shopping_qty = norm.get("shopping_qty")
            ing.shopping_unit = norm.get("shopping_unit")
```

**Step 6: Auto-trigger normalization for AI-generated recipes**

In `_ai_recipe_received()` (line 921 of `recipes_tab.py`), after creating the dialog but before `exec()`, we could auto-trigger normalization. However, this adds complexity and another API call. Instead, rely on the user clicking "Normalize for Shopping" in the dialog. This keeps it simple and user-controlled.

**Step 7: Test manually**

Run: `python main.py`
1. Open a recipe in edit mode
2. Click "Normalize for Shopping"
3. Verify the confirmation message appears
4. Save the recipe
5. Check the database: `sqlite3 ~/.meal_planner/meal_planner.db "SELECT name, shopping_name, shopping_qty, shopping_unit FROM recipe_ingredients WHERE shopping_name IS NOT NULL"`

**Step 8: Commit**

```bash
git add meal_planner/core/recipes.py meal_planner/gui/recipes_tab.py
git commit -m "feat: wire ingredient normalization into recipe save flow"
```

---

### Task 7: Update shopping list to use normalized fields

**Files:**
- Modify: `meal_planner/core/shopping_list.py:36-53` (ingredient aggregation)
- Modify: `meal_planner/core/shopping_list.py:110-145` (`get_ingredient_sources()`)

**Step 1: Update the ingredient query in `generate()` to fetch normalized fields**

In `meal_planner/core/shopping_list.py`, change the query at line 41-44:

```python
ings = conn.execute(
    """SELECT name, quantity, unit, estimated_price,
              shopping_name, shopping_qty, shopping_unit
       FROM recipe_ingredients WHERE recipe_id = ?""",
    (entry.recipe_id,),
).fetchall()
```

**Step 2: Use normalized fields for aggregation key and quantities**

Change the aggregation logic at lines 45-51:

```python
for ing in ings:
    # Use normalized shopping fields when available, fall back to raw
    s_name = (ing["shopping_name"] or ing["name"]).lower().strip()
    s_unit = (ing["shopping_unit"] or ing["unit"] or "").lower().strip()
    s_qty = ing["shopping_qty"] if ing["shopping_qty"] is not None else (ing["quantity"] or 0)

    key = (s_name, s_unit)
    qty = s_qty * entry.servings
    required[key] += qty
    if ing["estimated_price"] is not None and key not in ingredient_prices:
        ingredient_prices[key] = ing["estimated_price"]
```

**Step 3: Update `get_ingredient_sources()` to use normalized names**

In `get_ingredient_sources()`, update the query and key logic similarly:

```python
ings = conn.execute(
    """SELECT name, quantity, unit, shopping_name, shopping_qty, shopping_unit
       FROM recipe_ingredients WHERE recipe_id = ?""",
    (entry.recipe_id,),
).fetchall()
for ing in ings:
    key = (ing["shopping_name"] or ing["name"]).lower().strip()
    qty = (ing["shopping_qty"] if ing["shopping_qty"] is not None else (ing["quantity"] or 0)) * entry.servings
    unit = (ing["shopping_unit"] or ing["unit"] or "").lower().strip()
    sources[key].append((
        entry.recipe_id,
        entry.recipe_name or "Unknown Recipe",
        entry.date,
        entry.meal_slot,
        qty,
        unit,
    ))
```

**Step 4: Test manually**

Run: `python main.py`
1. Open a recipe, click "Normalize for Shopping", save
2. Add that recipe to the meal plan
3. Generate shopping list
4. Verify ingredients appear with their normalized names/units
5. Verify a non-normalized recipe still works (falls back to raw names)

**Step 5: Commit**

```bash
git add meal_planner/core/shopping_list.py
git commit -m "feat: use normalized ingredient fields in shopping list generation"
```

---

### Task 8: Add bulk normalization for existing recipes

**Files:**
- Modify: `meal_planner/gui/recipes_tab.py` (add menu action or button)
- Modify: `meal_planner/core/recipes.py` (add helper to get un-normalized recipes)

**Step 1: Add `get_unnormalized_recipes()` to recipes core**

In `meal_planner/core/recipes.py`, add:

```python
def get_unnormalized_recipes() -> list[Recipe]:
    """Return recipes that have ingredients without normalized shopping fields."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT DISTINCT r.id FROM recipes r
               JOIN recipe_ingredients ri ON ri.recipe_id = r.id
               WHERE ri.shopping_name IS NULL"""
        ).fetchall()
        recipe_ids = [row["id"] for row in rows]
        return [get(rid) for rid in recipe_ids if get(rid)]
    finally:
        conn.close()
```

**Step 2: Add "Normalize All Recipes" button to RecipesTab**

In the RecipesTab toolbar/button area, add a button:

```python
self.normalize_all_btn = QPushButton("Normalize All for Shopping")
self.normalize_all_btn.setToolTip("Use AI to normalize ingredients in all recipes that haven't been normalized yet")
self.normalize_all_btn.clicked.connect(self._normalize_all_recipes)
```

**Step 3: Implement `_normalize_all_recipes()`**

```python
def _normalize_all_recipes(self):
    """Normalize ingredients for all recipes missing shopping fields."""
    recipes = recipes_core.get_unnormalized_recipes()
    if not recipes:
        QMessageBox.information(self, "Up to Date", "All recipes already have normalized ingredients.")
        return
    reply = QMessageBox.question(
        self, "Normalize All",
        f"Normalize ingredients in {len(recipes)} recipe(s)?\n"
        "This will make one AI call per recipe.",
        QMessageBox.Yes | QMessageBox.No,
    )
    if reply != QMessageBox.Yes:
        return

    self.normalize_all_btn.setEnabled(False)
    self.normalize_all_btn.setText(f"Normalizing 0/{len(recipes)}...")

    def do_bulk_normalize():
        from meal_planner.core import ai_assistant
        results = []
        for i, recipe in enumerate(recipes):
            norm_data = ai_assistant.normalize_ingredients(recipe.ingredients)
            if norm_data:
                for j, ing in enumerate(recipe.ingredients):
                    if j < len(norm_data):
                        ing.shopping_name = norm_data[j].get("shopping_name")
                        ing.shopping_qty = norm_data[j].get("shopping_qty")
                        ing.shopping_unit = norm_data[j].get("shopping_unit")
                recipes_core.update(recipe)
            results.append((recipe.name, bool(norm_data)))
        return results

    self._bulk_norm_worker = AIWorker(do_bulk_normalize)
    self._bulk_norm_worker.finished.connect(self._bulk_normalize_done)
    self._bulk_norm_worker.error.connect(self._bulk_normalize_error)
    self._bulk_norm_worker.start()

def _bulk_normalize_done(self, results):
    self.normalize_all_btn.setEnabled(True)
    self.normalize_all_btn.setText("Normalize All for Shopping")
    success = sum(1 for _, ok in results if ok)
    QMessageBox.information(self, "Done", f"Normalized {success}/{len(results)} recipes.")

def _bulk_normalize_error(self, msg):
    self.normalize_all_btn.setEnabled(True)
    self.normalize_all_btn.setText("Normalize All for Shopping")
    QMessageBox.warning(self, "Error", msg)
```

**Step 4: Test manually**

Run: `python main.py`
1. Ensure you have a few recipes with ingredients
2. Click "Normalize All for Shopping"
3. Confirm the dialog
4. Verify completion message shows correct count
5. Check database for populated `shopping_name` values

**Step 5: Commit**

```bash
git add meal_planner/core/recipes.py meal_planner/gui/recipes_tab.py
git commit -m "feat: add bulk normalization for existing recipes"
```

---

## Summary of All Changes

| File | Change |
|------|--------|
| `db/database.py` | Add migrations: `is_staple` on pantry, `shopping_name`/`shopping_qty`/`shopping_unit` on recipe_ingredients |
| `db/models.py` | Add `is_staple` to PantryItem, add `shopping_name`/`shopping_qty`/`shopping_unit` to RecipeIngredient |
| `core/pantry.py` | Include `is_staple` in add/update SQL |
| `core/recipes.py` | Include shopping fields in add/update SQL; add `get_unnormalized_recipes()` |
| `core/ai_assistant.py` | Add `normalize_ingredients()` function |
| `core/shopping_list.py` | Exclude staples; use normalized fields with fallback in `generate()` and `get_ingredient_sources()` |
| `gui/pantry_tab.py` | Add "Staple" checkbox to PantryItemDialog |
| `gui/recipes_tab.py` | Add "Normalize for Shopping" to RecipeEditDialog; add "Normalize All" to RecipesTab |
