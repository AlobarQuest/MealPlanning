# Starter Recipes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show a friendly empty state on the Recipes page when the library is empty, with a one-click "Load starter recipes" button that seeds 20 pre-built recipes.

**Architecture:** One new `POST /recipes/seed` route in `app/routers/recipes.py` that calls `seed_starter_recipes()`. The empty state in `app/templates/partials/recipe_list.html` is updated to show the button when the list is empty and no search query is active. No DB or core changes needed — `seed_starter_recipes()` is complete.

**Tech Stack:** FastAPI, Jinja2, HTMX

---

## Existing code to understand before starting

- `meal_planner/core/starter_recipes.py` — `seed_starter_recipes()` inserts 20 recipes if the `recipes` table is empty. Safe to call multiple times (no-op if recipes exist).
- `app/templates/partials/recipe_list.html` — currently shows "No recipes found." when list is empty. This is the file to update.
- `app/routers/recipes.py` — the `/recipes/list` route at line 92 returns `recipe_list.html` with `recipes`, `q`, and `selected_id`. The seed route goes here.
- `tests/test_recipes.py` — follow patterns for `authed_client` fixture.

---

### Task 1: Seed route and empty state

**Files:**
- Modify: `app/routers/recipes.py`
- Modify: `app/templates/partials/recipe_list.html`
- Test: `tests/test_recipes.py`

**Step 1: Write the failing tests**

Append to `tests/test_recipes.py`:

```python
def test_recipe_seed_inserts_starter_recipes(authed_client):
    # Ensure recipes table is empty first
    from meal_planner.core import recipes as recipes_core
    for r in recipes_core.get_all():
        recipes_core.delete(r.id)
    assert recipes_core.get_all() == []

    resp = authed_client.post("/recipes/seed")
    assert resp.status_code == 200
    # Should return the recipe list with recipes now in it
    assert "Classic Oatmeal" in resp.text or "Spaghetti" in resp.text


def test_recipe_seed_is_idempotent(authed_client):
    # Seed twice — should not error or duplicate
    authed_client.post("/recipes/seed")
    resp = authed_client.post("/recipes/seed")
    assert resp.status_code == 200
    from meal_planner.core import recipes as recipes_core
    all_recipes = recipes_core.get_all()
    names = [r.name for r in all_recipes]
    # "Classic Oatmeal with Berries" should appear exactly once
    assert names.count("Classic Oatmeal with Berries") == 1


def test_recipe_list_empty_state_shows_seed_button(authed_client):
    from meal_planner.core import recipes as recipes_core
    for r in recipes_core.get_all():
        recipes_core.delete(r.id)
    resp = authed_client.get("/recipes/list")
    assert resp.status_code == 200
    assert "Load starter recipes" in resp.text


def test_recipe_list_search_empty_hides_seed_button(authed_client):
    from meal_planner.core import recipes as recipes_core
    for r in recipes_core.get_all():
        recipes_core.delete(r.id)
    resp = authed_client.get("/recipes/list?q=nonexistentquery")
    assert resp.status_code == 200
    assert "Load starter recipes" not in resp.text
    assert "No recipes found" in resp.text
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_recipes.py::test_recipe_seed_inserts_starter_recipes \
                  tests/test_recipes.py::test_recipe_list_empty_state_shows_seed_button -v
```
Expected: FAIL — route not found.

**Step 3: Add the seed route to `app/routers/recipes.py`**

Add the import near the top of `app/routers/recipes.py` with the other core imports:

```python
from meal_planner.core.starter_recipes import seed_starter_recipes
```

Add the route after `recipes_list` (around line 98), before the `# ── Add` section:

```python
@router.post("/seed", response_class=HTMLResponse)
def recipes_seed(request: Request):
    seed_starter_recipes()
    recipe_list = recipes_core.get_all()
    return templates.TemplateResponse(request, "partials/recipe_list.html", {
        "recipes": recipe_list, "q": "", "selected_id": None,
    })
```

**Step 4: Update `app/templates/partials/recipe_list.html`**

Replace the current empty state at the bottom with a context-aware version:

Current file:
```html
{% if recipes %}
{% for recipe in recipes %}
<div class="recipe-list-item {{ 'active' if selected_id and selected_id == recipe.id }}"
     hx-get="{{ '/demo' if demo else '' }}/recipes/{{ recipe.id }}"
     hx-target="#recipe-detail"
     hx-push-url="false">
  <div class="recipe-list-thumb">
    {% if recipe.photo_path %}
    <img src="{{ recipe.photo_path }}" alt="{{ recipe.name }}">
    {% else %}
    📄
    {% endif %}
  </div>
  <div class="recipe-list-info">
    <div class="recipe-list-name">{{ recipe.name }}</div>
    {% if recipe.tags %}
    <div class="recipe-list-tags">
      {% for tag in recipe.tags.split(',')[:3] %}
      <span class="tag">{{ tag.strip() }}</span>
      {% endfor %}
    </div>
    {% endif %}
  </div>
</div>
{% endfor %}
{% else %}
<div style="padding:2rem;text-align:center;color:var(--color-text-muted);font-size:13px">
  No recipes found.
</div>
{% endif %}
```

Replace with:
```html
{% if recipes %}
{% for recipe in recipes %}
<div class="recipe-list-item {{ 'active' if selected_id and selected_id == recipe.id }}"
     hx-get="{{ '/demo' if demo else '' }}/recipes/{{ recipe.id }}"
     hx-target="#recipe-detail"
     hx-push-url="false">
  <div class="recipe-list-thumb">
    {% if recipe.photo_path %}
    <img src="{{ recipe.photo_path }}" alt="{{ recipe.name }}">
    {% else %}
    📄
    {% endif %}
  </div>
  <div class="recipe-list-info">
    <div class="recipe-list-name">{{ recipe.name }}</div>
    {% if recipe.tags %}
    <div class="recipe-list-tags">
      {% for tag in recipe.tags.split(',')[:3] %}
      <span class="tag">{{ tag.strip() }}</span>
      {% endfor %}
    </div>
    {% endif %}
  </div>
</div>
{% endfor %}
{% elif q %}
<div style="padding:2rem;text-align:center;color:var(--color-text-muted);font-size:13px">
  No recipes found.
</div>
{% else %}
<div style="padding:2rem;text-align:center;color:var(--color-text-muted);font-size:13px">
  <p style="margin-bottom:1rem">Your recipe library is empty.</p>
  {% if not demo %}
  <button class="btn btn-primary"
          hx-post="/recipes/seed"
          hx-target="#recipe-list">Load starter recipes</button>
  {% endif %}
</div>
{% endif %}
```

**Step 5: Run tests**

```bash
python3 -m pytest tests/test_recipes.py -v
```
Expected: all tests PASS including the 4 new ones.

**Step 6: Run full suite**

```bash
python3 -m pytest tests/ -q
```
Expected: all tests pass.

**Step 7: Commit**

```bash
git add app/routers/recipes.py app/templates/partials/recipe_list.html
git commit -m "feat: starter recipes empty state — seed 20 recipes on first use"
```

---

## Completion check

```bash
python3 -m pytest tests/ -q
```

All tests pass. Visit `/recipes` with an empty library to see the empty state and "Load starter recipes" button. Click it — 20 recipes appear. Clicking again is safe (no duplicates).
