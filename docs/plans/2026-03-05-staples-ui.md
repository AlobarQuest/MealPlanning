# Staples UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Staples view to the Pantry tab — a toggle between Inventory and Staples, with full CRUD and bulk need-to-buy status management.

**Architecture:** New `app/routers/staples.py` (prefix `/pantry/staples`) registered in `app/main.py` before the pantry router. The Pantry page gets a toggle that swaps `#pantry-view` between an inventory partial and the staples partial via HTMX. No changes to `meal_planner/core/staples.py` — it's complete.

**Tech Stack:** FastAPI, Jinja2, HTMX, SQLite via `meal_planner/core/staples.py`

---

## Existing code to understand before starting

- `meal_planner/core/staples.py` — full CRUD: `get_all()`, `get()`, `add()`, `update()`, `delete()`, `set_need_to_buy()`. `Staple` model: `id, name, category=None, preferred_store_id=None, need_to_buy=False`.
- `app/routers/pantry.py` — follow its patterns: `_ctx()`, `templates.TemplateResponse`, `Form(...)` params.
- `app/routers/stores.py` — follow its delete pattern (returns `HTMLResponse("")`).
- `app/templates/pantry.html` — will be restructured to add the toggle.
- `app/templates/partials/stores_rows.html` — follow its table row pattern.
- `tests/test_stores.py` — follow its test patterns (authed_client fixture).
- `tests/conftest.py` — understand `authed_client` fixture.

---

### Task 1: Staples router — list, add, edit, delete

**Files:**
- Create: `app/routers/staples.py`
- Create: `app/templates/partials/staples_list.html`
- Create: `app/templates/partials/staple_dialog.html`
- Modify: `app/main.py`
- Test: `tests/test_staples.py`

**Step 1: Write the failing tests**

Create `tests/test_staples.py`:

```python
from meal_planner.core import staples as staples_core
from meal_planner.db.models import Staple


def test_staples_list_returns_200(authed_client):
    resp = authed_client.get("/pantry/staples")
    assert resp.status_code == 200
    assert "staple" in resp.text.lower() or "on hand" in resp.text.lower()


def test_staples_add_form_returns_dialog(authed_client):
    resp = authed_client.get("/pantry/staples/add")
    assert resp.status_code == 200
    assert "<dialog" in resp.text


def test_staples_add_saves_staple(authed_client):
    resp = authed_client.post("/pantry/staples/add", data={"name": "Olive Oil"})
    assert resp.status_code == 200
    assert "Olive Oil" in resp.text


def test_staples_edit_form_returns_dialog(authed_client):
    staples_core.add(Staple(id=None, name="Salt"))
    staple = staples_core.get_all()[0]
    resp = authed_client.get(f"/pantry/staples/{staple.id}/edit")
    assert resp.status_code == 200
    assert "Salt" in resp.text


def test_staples_edit_saves_changes(authed_client):
    staples_core.add(Staple(id=None, name="Pepper"))
    staple = staples_core.get_all()[-1]
    resp = authed_client.post(f"/pantry/staples/{staple.id}/edit", data={"name": "Black Pepper"})
    assert resp.status_code == 200
    assert "Black Pepper" in resp.text


def test_staples_delete_removes_staple(authed_client):
    staples_core.add(Staple(id=None, name="DeleteMe"))
    staple = next(s for s in staples_core.get_all() if s.name == "DeleteMe")
    resp = authed_client.delete(f"/pantry/staples/{staple.id}")
    assert resp.status_code == 200
    assert resp.text.strip() == ""
    assert staples_core.get(staple.id) is None
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_staples.py -v
```
Expected: errors — `app/routers/staples.py` doesn't exist yet.

**Step 3: Create the router**

Create `app/routers/staples.py`:

```python
"""Staples router — CRUD for pantry staples, nested under /pantry/staples."""
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core import staples as staples_core
from meal_planner.db.models import Staple

router = APIRouter(prefix="/pantry/staples", tags=["staples"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _all_staples():
    return staples_core.get_all()


@router.get("", response_class=HTMLResponse)
def staples_list(request: Request):
    return templates.TemplateResponse(request, "partials/staples_list.html", {
        "staples": _all_staples(), "demo": False,
    })


@router.get("/add", response_class=HTMLResponse)
def staples_add_form(request: Request):
    return templates.TemplateResponse(request, "partials/staple_dialog.html", {
        "staple": None,
    })


@router.post("/add", response_class=HTMLResponse)
def staples_add(request: Request, name: str = Form(...)):
    staples_core.add(Staple(id=None, name=name.strip()))
    return templates.TemplateResponse(request, "partials/staples_list.html", {
        "staples": _all_staples(), "demo": False,
    })


@router.get("/{staple_id}/edit", response_class=HTMLResponse)
def staples_edit_form(request: Request, staple_id: int):
    return templates.TemplateResponse(request, "partials/staple_dialog.html", {
        "staple": staples_core.get(staple_id),
    })


@router.post("/{staple_id}/edit", response_class=HTMLResponse)
def staples_edit(request: Request, staple_id: int, name: str = Form(...)):
    staple = staples_core.get(staple_id)
    staple.name = name.strip()
    staples_core.update(staple)
    return templates.TemplateResponse(request, "partials/staples_list.html", {
        "staples": _all_staples(), "demo": False,
    })


@router.delete("/{staple_id}", response_class=HTMLResponse)
def staples_delete(staple_id: int):
    staples_core.delete(staple_id)
    return HTMLResponse("")
```

**Step 4: Create the staples list partial**

Create `app/templates/partials/staples_list.html`:

```html
<div class="toolbar" id="staples-toolbar">
  {% if not demo %}
  <button class="btn btn-primary"
          hx-get="/pantry/staples/add"
          hx-target="#modal-container">+ Add Staple</button>
  <button id="btn-mark-needed" class="btn btn-secondary" disabled
          hx-post="/pantry/staples/bulk-status"
          hx-include="[name='staple_ids']:checked"
          hx-vals='{"need": "1"}'
          hx-target="#pantry-view">Mark as Needed</button>
  <button id="btn-mark-onhand" class="btn btn-secondary" disabled
          hx-post="/pantry/staples/bulk-status"
          hx-include="[name='staple_ids']:checked"
          hx-vals='{"need": "0"}'
          hx-target="#pantry-view">Mark as On Hand</button>
  {% endif %}
</div>

<table>
  <thead>
    <tr>
      {% if not demo %}<th style="width:2rem"></th>{% endif %}
      <th>Name</th>
      <th>Status</th>
      {% if not demo %}<th></th>{% endif %}
    </tr>
  </thead>
  <tbody>
    {% for staple in staples %}
    <tr id="staple-row-{{ staple.id }}">
      {% if not demo %}
      <td><input type="checkbox" name="staple_ids" value="{{ staple.id }}"
                 onchange="updateBulkButtons()"></td>
      {% endif %}
      <td>{{ staple.name }}</td>
      <td>
        <span class="tag {{ 'tag-needed' if staple.need_to_buy else 'tag-onhand' }}">
          {{ 'Needed' if staple.need_to_buy else 'On Hand' }}
        </span>
      </td>
      {% if not demo %}
      <td style="white-space:nowrap">
        <button class="btn btn-secondary btn-sm"
                hx-get="/pantry/staples/{{ staple.id }}/edit"
                hx-target="#modal-container">Edit</button>
        <button class="btn btn-danger btn-sm"
                hx-delete="/pantry/staples/{{ staple.id }}"
                hx-target="#staple-row-{{ staple.id }}"
                hx-swap="outerHTML"
                hx-confirm="Delete {{ staple.name }}?">Del</button>
      </td>
      {% endif %}
    </tr>
    {% else %}
    <tr>
      <td colspan="{{ 4 if not demo else 2 }}"
          style="text-align:center;color:#94a3b8;padding:2rem">
        No staples yet. Add items you always keep on hand.
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<script>
function updateBulkButtons() {
  const any = document.querySelectorAll('[name="staple_ids"]:checked').length > 0;
  document.getElementById('btn-mark-needed').disabled = !any;
  document.getElementById('btn-mark-onhand').disabled = !any;
}
</script>
```

**Step 5: Create the staple dialog partial**

Create `app/templates/partials/staple_dialog.html`:

```html
<dialog>
  <form method="post"
        action="{{ '/pantry/staples/' + staple.id|string + '/edit' if staple else '/pantry/staples/add' }}"
        hx-post="{{ '/pantry/staples/' + staple.id|string + '/edit' if staple else '/pantry/staples/add' }}"
        hx-target="#pantry-view"
        hx-on::after-request="this.closest('dialog').remove()">
    <h3>{{ 'Edit Staple' if staple else 'Add Staple' }}</h3>
    <label>Name
      <input type="text" name="name" value="{{ staple.name if staple else '' }}"
             required autofocus>
    </label>
    <div class="dialog-actions">
      <button type="submit" class="btn btn-primary">Save</button>
      <button type="button" class="btn btn-secondary"
              onclick="this.closest('dialog').remove()">Cancel</button>
    </div>
  </form>
</dialog>
```

**Step 6: Register the router in main.py**

Modify `app/main.py` — add import and include BEFORE the pantry router:

```python
from app.routers import auth, pantry, recipes, meal_plan, shopping, stores, settings, demo, help, admin, staples

# ... (after existing includes, but before pantry OR add before pantry)
app.include_router(staples.router)   # must be before pantry router
app.include_router(pantry.router)
```

**Step 7: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_staples.py -v
```
Expected: all 6 tests PASS.

**Step 8: Run full suite to check for regressions**

```bash
python3 -m pytest tests/ -q
```
Expected: 57 passed.

**Step 9: Commit**

```bash
git add app/routers/staples.py app/templates/partials/staples_list.html \
        app/templates/partials/staple_dialog.html app/main.py tests/test_staples.py
git commit -m "feat: staples router — list, add, edit, delete"
```

---

### Task 2: Bulk status route

**Files:**
- Modify: `app/routers/staples.py`
- Modify: `tests/test_staples.py`

**Step 1: Add test for bulk-status**

Append to `tests/test_staples.py`:

```python
def test_staples_bulk_status_mark_needed(authed_client):
    id1 = staples_core.add(Staple(id=None, name="Flour"))
    id2 = staples_core.add(Staple(id=None, name="Sugar"))
    resp = authed_client.post("/pantry/staples/bulk-status", data={
        "staple_ids": [str(id1), str(id2)], "need": "1"
    })
    assert resp.status_code == 200
    assert staples_core.get(id1).need_to_buy is True
    assert staples_core.get(id2).need_to_buy is True
    assert "Needed" in resp.text


def test_staples_bulk_status_mark_onhand(authed_client):
    staple_id = staples_core.add(Staple(id=None, name="Vinegar", need_to_buy=True))
    resp = authed_client.post("/pantry/staples/bulk-status", data={
        "staple_ids": [str(staple_id)], "need": "0"
    })
    assert resp.status_code == 200
    assert staples_core.get(staple_id).need_to_buy is False
```

**Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_staples.py::test_staples_bulk_status_mark_needed -v
```
Expected: FAIL — route not found.

**Step 3: Add the route to `app/routers/staples.py`**

Add after the delete route:

```python
from typing import List
from fastapi import APIRouter, Request, Form
# (List is from typing — add to imports)

@router.post("/bulk-status", response_class=HTMLResponse)
def staples_bulk_status(
    request: Request,
    staple_ids: List[int] = Form(default=[]),
    need: int = Form(...),
):
    for sid in staple_ids:
        staples_core.set_need_to_buy(sid, bool(need))
    return templates.TemplateResponse(request, "partials/staples_list.html", {
        "staples": _all_staples(), "demo": False,
    })
```

**Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_staples.py -v
```
Expected: all 8 tests PASS.

**Step 5: Commit**

```bash
git add app/routers/staples.py tests/test_staples.py
git commit -m "feat: staples bulk-status route"
```

---

### Task 3: Pantry page toggle UI

**Files:**
- Modify: `app/templates/pantry.html`
- Create: `app/templates/partials/pantry_inventory.html`
- Modify: `app/routers/pantry.py`
- Add CSS: `app/static/style.css`

**Step 1: Extract inventory partial**

Move the toolbar + table from `app/templates/pantry.html` into a new file `app/templates/partials/pantry_inventory.html`:

```html
<div class="toolbar">
  <select name="location"
          hx-get="/pantry/rows"
          hx-target="#pantry-tbody"
          hx-include="[name='category']">
    {% for loc in locations %}
      <option value="{{ loc }}" {{ 'selected' if loc == filter_location }}>
        {{ loc or 'All Locations' }}
      </option>
    {% endfor %}
  </select>

  <select name="category"
          hx-get="/pantry/rows"
          hx-target="#pantry-tbody"
          hx-include="[name='location']">
    {% for cat in categories %}
      <option value="{{ cat }}" {{ 'selected' if cat == filter_category }}>
        {{ cat or 'All Categories' }}
      </option>
    {% endfor %}
  </select>

  {% if not demo %}
  <button class="btn btn-primary"
          hx-get="/pantry/add"
          hx-target="#modal-container">+ Add Item</button>

  <label class="btn btn-secondary" style="cursor:pointer">
    Import CSV
    <input type="file" name="file" accept=".csv" style="display:none"
           hx-post="/pantry/import"
           hx-target="#pantry-tbody"
           hx-encoding="multipart/form-data"
           hx-trigger="change">
  </label>
  {% endif %}

  <span class="htmx-indicator"><span class="spinner"></span></span>
</div>

<table>
  <thead>
    <tr>
      <th>Name</th>
      <th>Brand</th>
      <th>Category</th>
      <th>Location</th>
      <th>Qty</th>
      <th>Unit</th>
      <th>Best By</th>
      <th>Store</th>
      {% if not demo %}<th></th>{% endif %}
    </tr>
  </thead>
  <tbody id="pantry-tbody">
    {% include "partials/pantry_rows.html" %}
  </tbody>
</table>
```

**Step 2: Rewrite `app/templates/pantry.html`**

```html
{% extends "base.html" %}
{% block title %}Pantry — Meal Planner{% endblock %}
{% block content %}

<div class="view-toggle">
  <button class="view-toggle-btn {{ 'active' if active_view != 'staples' }}"
          hx-get="/pantry/inventory"
          hx-target="#pantry-view">Inventory</button>
  <button class="view-toggle-btn {{ 'active' if active_view == 'staples' }}"
          hx-get="/pantry/staples"
          hx-target="#pantry-view">Staples</button>
</div>

<div id="pantry-view">
  {% include "partials/pantry_inventory.html" %}
</div>

{% endblock %}
```

**Step 3: Add `/pantry/inventory` route to `app/routers/pantry.py`**

Add this route after `pantry_page`:

```python
@router.get("/inventory", response_class=HTMLResponse)
def pantry_inventory(request: Request, location: str = "", category: str = ""):
    items = pantry_core.get_all(location=location or None, category=category or None)
    stores = pantry_core.get_all_stores()
    expiring_ids = {i.id for i in pantry_core.get_expiring_soon(7)}
    return templates.TemplateResponse(request, "partials/pantry_inventory.html", {
        "items": items,
        "store_map": _store_map(stores),
        "locations": [""] + pantry_core.get_locations(),
        "categories": [""] + pantry_core.get_categories(),
        "filter_location": location,
        "filter_category": category,
        "today": _today(),
        "expiring_ids": expiring_ids,
        "demo": False,
    })
```

**Step 4: Add CSS for the toggle**

Append to `app/static/style.css`:

```css
/* ─── View toggle ────────────────────────────────────────────────────────── */
.view-toggle { display: flex; gap: 4px; margin-bottom: 1rem; }
.view-toggle-btn { background: var(--color-surface); border: 1px solid var(--color-border);
                   border-radius: var(--radius-md); padding: 6px 16px; font-size: 13px;
                   font-weight: 500; cursor: pointer; color: var(--color-text-muted); }
.view-toggle-btn.active { background: var(--color-accent); color: #fff; border-color: var(--color-accent); }

/* ─── Staple status tags ─────────────────────────────────────────────────── */
.tag-needed { background: #fef3c7; color: #92400e; }
.tag-onhand { background: #d1fae5; color: #065f46; }
```

**Step 5: Verify manually**

Start the app and visit `/pantry`. Confirm:
- Toggle "Inventory / Staples" appears at the top
- Clicking "Staples" swaps to the staples view
- Clicking "Inventory" swaps back

**Step 6: Run full test suite**

```bash
python3 -m pytest tests/ -q
```
Expected: all tests pass (57+).

**Step 7: Commit**

```bash
git add app/templates/pantry.html app/templates/partials/pantry_inventory.html \
        app/routers/pantry.py app/static/style.css
git commit -m "feat: pantry toggle — Inventory / Staples view switcher"
```

---

### Task 4: Demo mode support

**Files:**
- Modify: `app/routers/demo.py`
- Modify: `tests/test_staples.py`

**Step 1: Add demo test**

Append to `tests/test_staples.py`:

```python
def test_demo_staples_accessible_without_auth():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.get("/demo/pantry/staples", follow_redirects=False)
    assert resp.status_code == 200


def test_demo_staples_hides_write_buttons():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.get("/demo/pantry/staples")
    assert "Add Staple" not in resp.text
    assert "Mark as Needed" not in resp.text
```

**Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_staples.py::test_demo_staples_accessible_without_auth -v
```
Expected: FAIL — route not found.

**Step 3: Add demo staples route to `app/routers/demo.py`**

Add after the existing demo_recipes routes, before `# ── Meal plan`:

```python
@router.get("/pantry/staples", response_class=HTMLResponse)
def demo_staples(request: Request):
    with override_db_path(_demo_db_path()):
        staple_list = staples_core.get_all()
    return templates.TemplateResponse(request, "partials/staples_list.html", {
        "staples": staple_list, "demo": True,
    })
```

Add the import at the top of `app/routers/demo.py` with the other core imports:

```python
from meal_planner.core import staples as staples_core
```

Also update `app/dependencies.py` to ensure `/demo/pantry/staples` is covered by the existing `/demo` public prefix (check that `_PUBLIC_PREFIXES` includes `/demo` — it should already).

**Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_staples.py -v
```
Expected: all 10 tests PASS.

**Step 5: Run full suite**

```bash
python3 -m pytest tests/ -q
```
Expected: all tests pass.

**Step 6: Commit**

```bash
git add app/routers/demo.py tests/test_staples.py
git commit -m "feat: demo mode for staples view"
```

---

## Completion check

```bash
python3 -m pytest tests/ -q
```

All tests should pass. Visit `/pantry`, toggle to Staples, add a staple, mark it as needed, check that it appears on the shopping list.
