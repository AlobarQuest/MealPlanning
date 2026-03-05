# Known Prices UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Price Book" section to the Stores tab — a global price list with manual entry and AI-powered receipt import.

**Architecture:** New `app/routers/known_prices.py` (prefix `/stores/prices`) registered in `app/main.py` before the stores router. The Stores page gets a second section below the existing table. Receipt parsing uses a new `parse_receipt()` function added to `meal_planner/core/ai_assistant.py`. No changes to `meal_planner/core/known_prices.py` — it's complete.

**Tech Stack:** FastAPI, Jinja2, HTMX, SQLite via `meal_planner/core/known_prices.py`, Anthropic Claude API

---

## Existing code to understand before starting

- `meal_planner/core/known_prices.py` — full CRUD: `get_all()`, `upsert()`, `bulk_upsert()`, `delete()`. `KnownPrice` model: `id, item_name, unit_price (float), unit=None, store_id=None, last_updated=None`.
- `meal_planner/core/ai_assistant.py` — follow `_get_client()`, `_parse_recipe_json()` patterns. Model is `claude-opus-4-5-20251101`.
- `app/routers/stores.py` — follow patterns for routes and templates.
- `app/templates/stores.html` — will get a Price Book section added.
- `app/templates/partials/stores_rows.html` — example of a rows partial pattern.
- `tests/test_stores.py` — follow for test patterns.

---

### Task 1: Known prices router — list, add, delete

**Files:**
- Create: `app/routers/known_prices.py`
- Create: `app/templates/partials/price_list.html`
- Create: `app/templates/partials/price_dialog.html`
- Modify: `app/main.py`
- Modify: `app/templates/stores.html`
- Test: `tests/test_known_prices.py`

**Step 1: Write the failing tests**

Create `tests/test_known_prices.py`:

```python
from meal_planner.core import known_prices as prices_core
from meal_planner.core import stores as stores_core
from meal_planner.db.models import Store


def test_prices_list_renders_in_stores_page(authed_client):
    resp = authed_client.get("/stores")
    assert resp.status_code == 200
    assert "price book" in resp.text.lower() or "prices" in resp.text.lower()


def test_prices_list_partial_returns_200(authed_client):
    resp = authed_client.get("/stores/prices")
    assert resp.status_code == 200


def test_prices_add_form_returns_dialog(authed_client):
    resp = authed_client.get("/stores/prices/add")
    assert resp.status_code == 200
    assert "<dialog" in resp.text


def test_prices_add_saves_price(authed_client):
    resp = authed_client.post("/stores/prices/add", data={
        "item_name": "Olive Oil", "unit_price": "8.99", "unit": "bottle", "store_id": ""
    })
    assert resp.status_code == 200
    assert "Olive Oil" in resp.text


def test_prices_delete_removes_price(authed_client):
    prices_core.upsert("DeleteMe", 1.99)
    price = next(p for p in prices_core.get_all() if p.item_name == "DeleteMe")
    resp = authed_client.delete(f"/stores/prices/{price.id}")
    assert resp.status_code == 200
    assert resp.text.strip() == ""
    assert prices_core.get_by_name("DeleteMe") is None


def test_prices_filter_by_store(authed_client):
    store_id = stores_core.add(Store(id=None, name="FilterStore"))
    prices_core.upsert("Butter", 3.49, store_id=store_id)
    resp = authed_client.get(f"/stores/prices?store_id={store_id}")
    assert resp.status_code == 200
    assert "Butter" in resp.text
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_known_prices.py -v
```
Expected: errors — router doesn't exist yet.

**Step 3: Create the router**

Create `app/routers/known_prices.py`:

```python
"""Known prices router — Price Book section within the Stores tab."""
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core import known_prices as prices_core
from meal_planner.core import stores as stores_core

router = APIRouter(prefix="/stores/prices", tags=["known_prices"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _price_list_ctx(store_id: int = 0):
    all_prices = prices_core.get_all()
    if store_id:
        all_prices = [p for p in all_prices if p.store_id == store_id]
    store_map = {s.id: s.name for s in stores_core.get_all()}
    return {"prices": all_prices, "store_map": store_map,
            "stores": stores_core.get_all(), "filter_store_id": store_id}


@router.get("", response_class=HTMLResponse)
def prices_list(request: Request, store_id: int = 0):
    return templates.TemplateResponse(request, "partials/price_list.html", {
        **_price_list_ctx(store_id), "demo": False,
    })


@router.get("/add", response_class=HTMLResponse)
def prices_add_form(request: Request):
    return templates.TemplateResponse(request, "partials/price_dialog.html", {
        "stores": stores_core.get_all(),
    })


@router.post("/add", response_class=HTMLResponse)
def prices_add(
    request: Request,
    item_name: str = Form(...),
    unit_price: float = Form(...),
    unit: str = Form(""),
    store_id: str = Form(""),
):
    prices_core.upsert(
        item_name.strip(),
        unit_price,
        unit=unit.strip() or None,
        store_id=int(store_id) if store_id else None,
    )
    return templates.TemplateResponse(request, "partials/price_list.html", {
        **_price_list_ctx(), "demo": False,
    })


@router.delete("/{price_id}", response_class=HTMLResponse)
def prices_delete(price_id: int):
    prices_core.delete(price_id)
    return HTMLResponse("")
```

**Step 4: Create the price list partial**

Create `app/templates/partials/price_list.html`:

```html
<div class="toolbar">
  {% if not demo %}
  <select hx-get="/stores/prices"
          hx-target="#price-list-body"
          hx-swap="innerHTML"
          name="store_id">
    <option value="">All Stores</option>
    {% for store in stores %}
    <option value="{{ store.id }}" {{ 'selected' if filter_store_id == store.id }}>
      {{ store.name }}
    </option>
    {% endfor %}
  </select>
  <button class="btn btn-primary"
          hx-get="/stores/prices/add"
          hx-target="#modal-container">+ Add Price</button>
  <button class="btn btn-secondary"
          hx-get="/stores/prices/import"
          hx-target="#modal-container">Import from Receipt</button>
  {% endif %}
</div>

<table>
  <thead>
    <tr>
      <th>Item</th>
      <th>Price</th>
      <th>Unit</th>
      <th>Store</th>
      <th>Updated</th>
      {% if not demo %}<th></th>{% endif %}
    </tr>
  </thead>
  <tbody id="price-list-body">
    {% for price in prices %}
    <tr id="price-row-{{ price.id }}">
      <td>{{ price.item_name }}</td>
      <td>${{ "%.2f"|format(price.unit_price) }}</td>
      <td>{{ price.unit or '—' }}</td>
      <td>{{ store_map.get(price.store_id, '—') }}</td>
      <td style="font-size:12px;color:#94a3b8">{{ price.last_updated[:10] if price.last_updated else '—' }}</td>
      {% if not demo %}
      <td>
        <button class="btn btn-danger btn-sm"
                hx-delete="/stores/prices/{{ price.id }}"
                hx-target="#price-row-{{ price.id }}"
                hx-swap="outerHTML"
                hx-confirm="Delete price for {{ price.item_name }}?">Del</button>
      </td>
      {% endif %}
    </tr>
    {% else %}
    <tr>
      <td colspan="{{ 6 if not demo else 5 }}"
          style="text-align:center;color:#94a3b8;padding:2rem">
        No prices yet. Add manually or import from a receipt.
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

**Step 5: Create the add price dialog**

Create `app/templates/partials/price_dialog.html`:

```html
<dialog>
  <form hx-post="/stores/prices/add"
        hx-target="#price-list-body"
        hx-swap="innerHTML"
        hx-on::after-request="this.closest('dialog').remove()">
    <h3>Add Price</h3>
    <label>Item Name
      <input type="text" name="item_name" required autofocus>
    </label>
    <label>Price ($)
      <input type="number" name="unit_price" step="0.01" min="0" required>
    </label>
    <label>Unit (optional)
      <input type="text" name="unit" placeholder="e.g. bottle, lb, each">
    </label>
    <label>Store (optional)
      <select name="store_id">
        <option value="">— Any store —</option>
        {% for store in stores %}
        <option value="{{ store.id }}">{{ store.name }}</option>
        {% endfor %}
      </select>
    </label>
    <div class="dialog-actions">
      <button type="submit" class="btn btn-primary">Save</button>
      <button type="button" class="btn btn-secondary"
              onclick="this.closest('dialog').remove()">Cancel</button>
    </div>
  </form>
</dialog>
```

**Step 6: Add Price Book section to stores.html**

Modify `app/templates/stores.html` to add the Price Book below the existing table:

```html
{% extends "base.html" %}
{% block title %}Stores — Meal Planner{% endblock %}
{% block content %}

<div class="toolbar">
  {% if not demo %}
  <button class="btn btn-primary"
          hx-get="/stores/add"
          hx-target="#modal-container">+ Add Store</button>
  {% endif %}
</div>

<table>
  <thead>
    <tr>
      <th>Name</th>
      <th>Location</th>
      <th>Notes</th>
      {% if not demo %}<th></th>{% endif %}
    </tr>
  </thead>
  <tbody id="stores-tbody">
    {% include "partials/stores_rows.html" %}
  </tbody>
</table>

<h2 style="margin-top:2rem;margin-bottom:1rem;font-size:1.1rem;font-weight:600">Price Book</h2>
<div id="price-book">
  {% include "partials/price_list.html" %}
</div>

{% endblock %}
```

**Step 7: Register router in main.py — before the stores router**

Modify `app/main.py`:

```python
from app.routers import auth, pantry, recipes, meal_plan, shopping, stores, settings, demo, help, admin, staples, known_prices

# ...
app.include_router(staples.router)
app.include_router(known_prices.router)  # must be before stores router
app.include_router(pantry.router)
app.include_router(stores.router)
```

**Step 8: Run tests**

```bash
python3 -m pytest tests/test_known_prices.py -v
```
Expected: all 6 tests PASS.

**Step 9: Run full suite**

```bash
python3 -m pytest tests/ -q
```
Expected: all pass.

**Step 10: Commit**

```bash
git add app/routers/known_prices.py app/templates/partials/price_list.html \
        app/templates/partials/price_dialog.html app/templates/stores.html \
        app/main.py tests/test_known_prices.py
git commit -m "feat: price book — list, add, delete in stores tab"
```

---

### Task 2: Receipt import — AI parsing

**Files:**
- Modify: `meal_planner/core/ai_assistant.py`
- Create: `app/templates/partials/price_import_dialog.html`
- Modify: `app/routers/known_prices.py`
- Modify: `tests/test_known_prices.py`

**Step 1: Add parse_receipt to ai_assistant.py**

Open `meal_planner/core/ai_assistant.py`. After the existing `fetch_og_image` function (near end of file), add:

```python
def parse_receipt(text: str) -> list[dict]:
    """Extract grocery items and prices from receipt text using Claude.

    Returns a list of dicts: [{item_name, unit_price, unit}]
    unit may be None if not determinable from the receipt.
    Returns empty list if parsing fails or API key not set.
    """
    client = _get_client()
    prompt = f"""Extract all grocery items and their prices from this receipt text.
Return a JSON array of objects, each with:
- "item_name": string (the product name, cleaned up)
- "unit_price": number (price as a float, e.g. 2.99)
- "unit": string or null (e.g. "lb", "each", "bottle" — null if unknown)

Only include items that have a clear price. Skip subtotals, taxes, and totals.
Return ONLY the JSON array, no explanation.

Receipt text:
{text[:8000]}"""

    response = client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)

    try:
        items = json.loads(raw)
        return [
            {
                "item_name": str(i.get("item_name", "")).strip(),
                "unit_price": float(i.get("unit_price", 0)),
                "unit": i.get("unit") or None,
            }
            for i in items
            if i.get("item_name") and i.get("unit_price") is not None
        ]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
```

**Step 2: Add import dialog routes to known_prices.py**

Append to `app/routers/known_prices.py`:

```python
from meal_planner.core.ai_assistant import parse_receipt


@router.get("/import", response_class=HTMLResponse)
def prices_import_form(request: Request):
    return templates.TemplateResponse(request, "partials/price_import_dialog.html", {
        "stores": stores_core.get_all(),
        "extracted": None,
    })


@router.post("/import/parse", response_class=HTMLResponse)
def prices_import_parse(
    request: Request,
    receipt_text: str = Form(...),
    store_id: str = Form(""),
):
    extracted = parse_receipt(receipt_text)
    return templates.TemplateResponse(request, "partials/price_import_dialog.html", {
        "stores": stores_core.get_all(),
        "extracted": extracted,
        "store_id": store_id,
    })


@router.post("/import/save", response_class=HTMLResponse)
async def prices_import_save(request: Request):
    form = await request.form()
    store_id = form.get("store_id", "")
    store_id_int = int(store_id) if store_id else None

    items = []
    names = form.getlist("item_name")
    prices_raw = form.getlist("unit_price")
    units = form.getlist("unit")
    included = form.getlist("include")  # values are indices of checked items

    for i, (name, price, unit) in enumerate(zip(names, prices_raw, units)):
        if str(i) in included:
            try:
                items.append({
                    "item_name": name,
                    "unit_price": float(price),
                    "unit": unit or None,
                    "store_id": store_id_int,
                })
            except ValueError:
                pass

    if items:
        prices_core.bulk_upsert(items)

    return templates.TemplateResponse(request, "partials/price_list.html", {
        **_price_list_ctx(), "demo": False,
        "hx_retarget": "#price-book",
    })
```

**Step 3: Create the import dialog partial**

Create `app/templates/partials/price_import_dialog.html`:

```html
<dialog>
  {% if not extracted %}
  <!-- Step 1: paste receipt -->
  <form hx-post="/stores/prices/import/parse"
        hx-target="#modal-container">
    <h3>Import from Receipt</h3>
    <label>Store
      <select name="store_id">
        <option value="">— Select store —</option>
        {% for store in stores %}
        <option value="{{ store.id }}">{{ store.name }}</option>
        {% endfor %}
      </select>
    </label>
    <label>Paste receipt text
      <textarea name="receipt_text" rows="10"
                placeholder="Paste your receipt here…"
                required style="width:100%;font-size:12px;font-family:monospace"></textarea>
    </label>
    <div class="dialog-actions">
      <button type="submit" class="btn btn-primary">Extract Prices</button>
      <button type="button" class="btn btn-secondary"
              onclick="this.closest('dialog').remove()">Cancel</button>
    </div>
  </form>

  {% else %}
  <!-- Step 2: review extracted prices -->
  <form hx-post="/stores/prices/import/save"
        hx-target="#price-book"
        hx-on::after-request="this.closest('dialog').remove()">
    <h3>Review Extracted Prices</h3>
    <input type="hidden" name="store_id" value="{{ store_id or '' }}">
    <p style="font-size:13px;color:#64748b;margin-bottom:1rem">
      Uncheck items you don't want to save.
    </p>
    <div style="max-height:50vh;overflow-y:auto">
    <table>
      <thead>
        <tr><th></th><th>Item</th><th>Price</th><th>Unit</th></tr>
      </thead>
      <tbody>
        {% for item in extracted %}
        <tr>
          <td><input type="checkbox" name="include" value="{{ loop.index0 }}" checked></td>
          <td><input type="hidden" name="item_name" value="{{ item.item_name }}">{{ item.item_name }}</td>
          <td><input type="hidden" name="unit_price" value="{{ item.unit_price }}">${{ "%.2f"|format(item.unit_price) }}</td>
          <td><input type="hidden" name="unit" value="{{ item.unit or '' }}">{{ item.unit or '—' }}</td>
        </tr>
        {% else %}
        <tr><td colspan="4" style="text-align:center;color:#94a3b8;padding:1rem">
          No prices could be extracted. Try pasting more of the receipt.
        </td></tr>
        {% endfor %}
      </tbody>
    </table>
    </div>
    <div class="dialog-actions">
      <button type="submit" class="btn btn-primary">Save Selected</button>
      <button type="button" class="btn btn-secondary"
              onclick="this.closest('dialog').remove()">Cancel</button>
    </div>
  </form>
  {% endif %}
</dialog>
```

**Step 4: Add tests for receipt import**

Append to `tests/test_known_prices.py`:

```python
def test_prices_import_form_returns_dialog(authed_client):
    resp = authed_client.get("/stores/prices/import")
    assert resp.status_code == 200
    assert "<dialog" in resp.text
    assert "receipt" in resp.text.lower()


def test_prices_import_save_bulk_upserts(authed_client):
    resp = authed_client.post("/stores/prices/import/save", data={
        "store_id": "",
        "item_name": ["Eggs", "Milk"],
        "unit_price": ["3.99", "4.49"],
        "unit": ["dozen", "gallon"],
        "include": ["0", "1"],
    })
    assert resp.status_code == 200
    eggs = prices_core.get_by_name("Eggs")
    assert eggs is not None
    assert eggs.unit_price == 3.99


def test_prices_import_save_skips_unchecked(authed_client):
    resp = authed_client.post("/stores/prices/import/save", data={
        "store_id": "",
        "item_name": ["Butter", "Cheese"],
        "unit_price": ["5.99", "7.99"],
        "unit": ["", ""],
        "include": ["0"],  # only first item checked
    })
    assert resp.status_code == 200
    assert prices_core.get_by_name("Butter") is not None
    assert prices_core.get_by_name("Cheese") is None
```

**Step 5: Run tests**

```bash
python3 -m pytest tests/test_known_prices.py -v
```
Expected: all 9 tests PASS. (The `parse` route calls the real AI — only the `save` and `form` routes are testable without mocking.)

**Step 6: Run full suite**

```bash
python3 -m pytest tests/ -q
```
Expected: all pass.

**Step 7: Commit**

```bash
git add meal_planner/core/ai_assistant.py app/routers/known_prices.py \
        app/templates/partials/price_import_dialog.html tests/test_known_prices.py
git commit -m "feat: receipt import — AI extraction of prices into price book"
```

---

### Task 3: Demo mode support

**Files:**
- Modify: `app/routers/demo.py`
- Modify: `tests/test_known_prices.py`

**Step 1: Add demo test**

Append to `tests/test_known_prices.py`:

```python
def test_demo_stores_shows_price_book():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.get("/demo/stores")
    assert resp.status_code == 200
    assert "price book" in resp.text.lower() or "prices" in resp.text.lower()
```

**Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_known_prices.py::test_demo_stores_shows_price_book -v
```
Expected: FAIL — demo stores page doesn't include prices yet.

**Step 3: Update demo stores route in `app/routers/demo.py`**

The demo stores route currently returns `stores.html` with `stores=store_list`. Since `stores.html` now includes `{% include "partials/price_list.html" %}`, we need to also pass prices. Update `demo_stores`:

```python
@router.get("/stores", response_class=HTMLResponse)
def demo_stores(request: Request):
    with override_db_path(_demo_db_path()):
        store_list = stores_core.get_all()
        price_list = known_prices_core.get_all()
        store_map = {s.id: s.name for s in store_list}
    return templates.TemplateResponse(request, "stores.html", _ctx(
        request, "stores",
        stores=store_list,
        prices=price_list,
        store_map=store_map,
        stores_list=store_list,  # for price list filter dropdown
        filter_store_id=0,
    ))
```

Add import at top of `app/routers/demo.py`:

```python
from meal_planner.core import known_prices as known_prices_core
```

Also update the non-demo `stores_page` in `app/routers/stores.py` to pass prices context:

```python
@router.get("", response_class=HTMLResponse)
def stores_page(request: Request):
    all_stores = stores_core.get_all()
    return templates.TemplateResponse(request, "stores.html", {
        "active_tab": "stores", "demo": False,
        "stores": all_stores,
        "prices": prices_core.get_all(),
        "store_map": {s.id: s.name for s in all_stores},
        "stores_list": all_stores,
        "filter_store_id": 0,
    })
```

Add import to `app/routers/stores.py`:

```python
from meal_planner.core import known_prices as prices_core
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_known_prices.py -v
```
Expected: all 10 tests PASS.

**Step 5: Run full suite**

```bash
python3 -m pytest tests/ -q
```
Expected: all pass.

**Step 6: Commit**

```bash
git add app/routers/demo.py app/routers/stores.py tests/test_known_prices.py
git commit -m "feat: demo mode for price book; pass prices context to stores page"
```

---

## Completion check

```bash
python3 -m pytest tests/ -q
```

All tests should pass. Visit `/stores`, scroll down to Price Book, add a price manually, then use Import from Receipt with a pasted grocery receipt.
