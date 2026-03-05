# UI Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modernise the Meal Planner web UI to a clean Notion/Linear-style aesthetic with a hybrid top-bar + sidebar nav, full-width content, and a redesigned recipe section with photo support.

**Architecture:** Full rewrite of `style.css` using CSS custom properties, restructure `base.html` for the new nav layout, redesign the recipe section templates for the three-zone detail view and thumbnail list, add `photo_path` to the DB and `Recipe` model, and wire up photo upload + og:image auto-fetch in the recipes router.

**Tech Stack:** FastAPI, Jinja2, HTMX 2.x, vanilla CSS, SQLite sqlite3, Python Pillow (image save), httpx (og:image fetch)

---

## Context

- All templates live in `app/templates/` and `app/templates/partials/`
- Single stylesheet: `app/static/style.css` (~160 lines, full rewrite)
- Recipe photos stored at `app/static/uploads/recipes/{recipe_id}.jpg`
- DB migrations use `try/except ALTER TABLE` in `meal_planner/db/database.py:init_db()`
- Tests live in `tests/` and use FastAPI `TestClient` with in-memory SQLite via `DB_PATH` env var
- Run tests: `pytest tests/ -v`
- Run app locally: `uvicorn app.main:app --reload --port 8080`
- Push to deploy: `git push origin clean-main:main`

---

## Task 1: Add photo_path to DB and Recipe model

**Files:**
- Modify: `meal_planner/db/models.py`
- Modify: `meal_planner/db/database.py`
- Modify: `meal_planner/core/recipes.py`
- Test: `tests/test_recipes.py`

**Step 1: Write a failing test**

Add to `tests/test_recipes.py`:

```python
def test_recipe_photo_path(db):
    from meal_planner.core import recipes as recipes_core
    from meal_planner.db.models import Recipe
    r = Recipe(id=None, name="Photo Test", photo_path="/static/uploads/recipes/1.jpg")
    recipe_id = recipes_core.add(r)
    fetched = recipes_core.get(recipe_id)
    assert fetched.photo_path == "/static/uploads/recipes/1.jpg"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_recipes.py::test_recipe_photo_path -v
```
Expected: FAIL — `Recipe` has no field `photo_path`

**Step 3: Add photo_path to the Recipe dataclass**

In `meal_planner/db/models.py`, add field to `Recipe`:

```python
@dataclass
class Recipe:
    id: Optional[int]
    name: str
    description: Optional[str] = None
    servings: int = 4
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    instructions: Optional[str] = None
    source_url: Optional[str] = None
    tags: Optional[str] = None
    rating: Optional[int] = None
    photo_path: Optional[str] = None        # ← add this line
    created_at: Optional[str] = None
    ingredients: list = field(default_factory=list)
```

**Step 4: Add DB migration in init_db()**

In `meal_planner/db/database.py`, add `photo_path` to the migrations loop (the `for col, table, col_type` block):

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
        ("photo_path", "recipes", "TEXT"),        # ← add this line
    ]:
```

**Step 5: Update core/recipes.py to read and write photo_path**

In `meal_planner/core/recipes.py`, find the `get()` function where it builds a `Recipe` from a DB row and add `photo_path=row["photo_path"]`. Find the `add()` and `update()` functions and include `photo_path` in the INSERT/UPDATE SQL and parameters.

Read `meal_planner/core/recipes.py` fully before editing to find the exact lines. The pattern will look like:

In `get()`:
```python
return Recipe(
    id=row["id"],
    name=row["name"],
    ...
    photo_path=row["photo_path"],   # ← add
    ...
)
```

In `add()` INSERT statement, add `photo_path` to columns and `recipe.photo_path` to values.

In `update()` UPDATE statement, add `photo_path = ?` and `recipe.photo_path` to params.

**Step 6: Run test to verify it passes**

```bash
pytest tests/test_recipes.py -v
```
Expected: all pass including `test_recipe_photo_path`

**Step 7: Commit**

```bash
git add meal_planner/db/models.py meal_planner/db/database.py meal_planner/core/recipes.py tests/test_recipes.py
git commit -m "feat: add photo_path field to Recipe model and DB"
```

---

## Task 2: Photo upload directory and static mount

**Files:**
- Modify: `app/main.py`
- Modify: `app/static/uploads/recipes/.gitkeep` (create)

**Step 1: Create the uploads directory with a .gitkeep**

```bash
mkdir -p app/static/uploads/recipes
touch app/static/uploads/recipes/.gitkeep
```

**Step 2: Add uploads dir to .gitignore to avoid committing images**

Add to `.gitignore`:
```
app/static/uploads/recipes/*.jpg
app/static/uploads/recipes/*.png
```

**Step 3: Ensure uploads directory is created at startup**

In `app/main.py`, inside the `lifespan` function after `init_db()`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Ensure photo upload directory exists
    uploads_dir = Path(__file__).parent / "static" / "uploads" / "recipes"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    ...
```

**Step 4: Add Pillow to requirements.txt**

```
Pillow>=10.0.0
```

Pillow is used to normalise uploaded images to JPEG regardless of input format.

**Step 5: Commit**

```bash
git add app/main.py requirements.txt app/static/uploads/recipes/.gitkeep .gitignore
git commit -m "feat: add recipe photo upload directory and Pillow dependency"
```

---

## Task 3: Photo upload in recipe add/edit routes

**Files:**
- Modify: `app/routers/recipes.py`
- Modify: `app/templates/partials/recipe_dialog.html`
- Test: `tests/test_recipes.py`

**Step 1: Write failing tests**

Add to `tests/test_recipes.py`:

```python
def test_add_recipe_with_photo(client, tmp_path):
    """Upload a minimal JPEG when adding a recipe."""
    import io
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    resp = client.post("/recipes/add", data={"name": "Photo Recipe", "servings": "2"},
                       files={"photo": ("test.jpg", buf, "image/jpeg")})
    assert resp.status_code in (200, 303)
    from meal_planner.core import recipes as recipes_core
    recipes = recipes_core.get_all()
    recipe = next((r for r in recipes if r.name == "Photo Recipe"), None)
    assert recipe is not None
    # photo_path should be set (or None if no upload dir in test env — acceptable)
```

**Step 2: Run test to confirm it fails**

```bash
pytest tests/test_recipes.py::test_add_recipe_with_photo -v
```

**Step 3: Add a photo save helper to recipes.py router**

Add this helper function near the top of `app/routers/recipes.py`, below the imports:

```python
from pathlib import Path as _Path
import io as _io

_UPLOADS_DIR = _Path(__file__).parent.parent / "static" / "uploads" / "recipes"


def _save_photo(recipe_id: int, file_bytes: bytes) -> str | None:
    """Save uploaded image as JPEG, return the static path or None on failure."""
    try:
        from PIL import Image
        img = Image.open(_io.BytesIO(file_bytes))
        img = img.convert("RGB")
        _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        dest = _UPLOADS_DIR / f"{recipe_id}.jpg"
        img.save(dest, "JPEG", quality=85)
        return f"/static/uploads/recipes/{recipe_id}.jpg"
    except Exception:
        return None
```

**Step 4: Update _recipe_from_form to accept UploadFile**

Change `recipes_add` and `recipe_edit` to use `UploadFile`:

```python
from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, File
from typing import Optional

@router.post("/add")
async def recipes_add(request: Request, photo: Optional[UploadFile] = File(None)):
    form = await request.form()
    recipe = _recipe_from_form(form)
    recipe_id = recipes_core.add(recipe)
    if photo and photo.filename:
        file_bytes = await photo.read()
        photo_path = _save_photo(recipe_id, file_bytes)
        if photo_path:
            saved = recipes_core.get(recipe_id)
            saved.photo_path = photo_path
            recipes_core.update(saved)
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=303)


@router.post("/{recipe_id}/edit", response_class=HTMLResponse)
async def recipe_edit(request: Request, recipe_id: int, photo: Optional[UploadFile] = File(None)):
    form = await request.form()
    recipe = _recipe_from_form(form, recipe_id=recipe_id)
    # Preserve existing photo_path if no new upload
    existing = recipes_core.get(recipe_id)
    recipe.photo_path = existing.photo_path if existing else None
    if photo and photo.filename:
        file_bytes = await photo.read()
        new_path = _save_photo(recipe_id, file_bytes)
        if new_path:
            recipe.photo_path = new_path
    recipes_core.update(recipe)
    updated = recipes_core.get(recipe_id)
    return templates.TemplateResponse(request, "partials/recipe_detail.html", {
        "recipe": updated, "demo": False,
    })
```

**Step 5: Add photo upload field to recipe_dialog.html**

In `app/templates/partials/recipe_dialog.html`, add `enctype="multipart/form-data"` to the `<form>` tag:

```html
<form method="post" action="{{ action }}"
      enctype="multipart/form-data"
      hx-post="{{ action }}"
      hx-encoding="multipart/form-data"
      ...>
```

Then add a photo field inside `.dialog-body`, after the Source URL group:

```html
<div class="form-group">
  <label>Photo</label>
  {% if recipe and recipe.photo_path %}
  <div style="margin-bottom:.5rem">
    <img src="{{ recipe.photo_path }}" alt="Current photo"
         style="width:80px;height:80px;object-fit:cover;border-radius:6px">
    <span style="font-size:.85rem;color:#64748b;margin-left:.5rem">Current photo</span>
  </div>
  {% endif %}
  <input type="file" name="photo" accept="image/jpeg,image/png">
  <small style="color:#94a3b8">JPG or PNG. Leave blank to keep existing photo.</small>
</div>
```

**Step 6: Run tests**

```bash
pytest tests/test_recipes.py -v
```
Expected: all pass

**Step 7: Commit**

```bash
git add app/routers/recipes.py app/templates/partials/recipe_dialog.html tests/test_recipes.py
git commit -m "feat: photo upload on recipe add/edit"
```

---

## Task 4: og:image auto-fetch on URL import

**Files:**
- Modify: `meal_planner/core/ai_assistant.py`
- Modify: `app/routers/recipes.py`
- Test: `tests/test_recipes.py`

**Step 1: Add og:image extractor to ai_assistant.py**

Add this function near `parse_recipe_url` in `meal_planner/core/ai_assistant.py`:

```python
def fetch_og_image(url: str) -> Optional[bytes]:
    """Attempt to download the og:image from a URL. Returns image bytes or None."""
    try:
        response = httpx.get(url, follow_redirects=True, timeout=15)
        response.raise_for_status()
        html = response.text
    except Exception:
        return None

    match = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE
    )
    if not match:
        # Also try content before property ordering
        match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            html, re.IGNORECASE
        )
    if not match:
        return None

    img_url = match.group(1)
    try:
        img_response = httpx.get(img_url, follow_redirects=True, timeout=15)
        img_response.raise_for_status()
        return img_response.content
    except Exception:
        return None
```

**Step 2: Use fetch_og_image in the ai/parse-url route**

In `app/routers/recipes.py`, update the `ai_parse_url` route to attempt og:image fetch and store the image bytes in the session context by passing it to the template (it will be used when the user saves the AI-previewed recipe):

```python
from meal_planner.core.ai_assistant import (
    parse_recipe_text, parse_recipe_url, generate_recipe, modify_recipe,
    fetch_og_image,
)

@router.post("/ai/parse-url", response_class=HTMLResponse)
def ai_parse_url(request: Request, url: str = Form(...)):
    recipe = parse_recipe_url(url)
    # Try to prefetch og:image; store bytes in a hidden field as base64
    og_image_b64 = None
    if recipe:
        img_bytes = fetch_og_image(url)
        if img_bytes:
            import base64
            og_image_b64 = base64.b64encode(img_bytes).decode()
    return templates.TemplateResponse(request, "partials/recipe_dialog.html", {
        "recipe": recipe,
        "ingredients": recipe.ingredients if recipe else [],
        "is_ai_preview": True,
        "og_image_b64": og_image_b64,
    })
```

**Step 3: Add hidden og_image field to recipe_dialog.html**

Inside the `<form>` in `recipe_dialog.html`, after the photo upload field:

```html
{% if og_image_b64 %}
<input type="hidden" name="og_image_b64" value="{{ og_image_b64 }}">
{% endif %}
```

**Step 4: Handle og_image_b64 in recipes_add route**

In the `recipes_add` handler, after saving the recipe, check for `og_image_b64` in the form if no photo was uploaded:

```python
@router.post("/add")
async def recipes_add(request: Request, photo: Optional[UploadFile] = File(None)):
    form = await request.form()
    recipe = _recipe_from_form(form)
    recipe_id = recipes_core.add(recipe)
    file_bytes = None
    if photo and photo.filename:
        file_bytes = await photo.read()
    elif form.get("og_image_b64"):
        import base64
        try:
            file_bytes = base64.b64decode(form["og_image_b64"])
        except Exception:
            file_bytes = None
    if file_bytes:
        photo_path = _save_photo(recipe_id, file_bytes)
        if photo_path:
            saved = recipes_core.get(recipe_id)
            saved.photo_path = photo_path
            recipes_core.update(saved)
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=303)
```

**Step 5: Run tests**

```bash
pytest tests/ -v
```
Expected: all pass

**Step 6: Commit**

```bash
git add meal_planner/core/ai_assistant.py app/routers/recipes.py app/templates/partials/recipe_dialog.html
git commit -m "feat: auto-fetch og:image when importing recipe from URL"
```

---

## Task 5: Rewrite style.css with new design system

**Files:**
- Modify: `app/static/style.css` (full rewrite)

No tests needed — visual only. Verify by running the app and checking all pages.

**Step 1: Replace the entire contents of style.css**

```css
/* ─── Design tokens ──────────────────────────────────────────────────────── */
:root {
  --color-bg:            #f8fafc;
  --color-surface:       #ffffff;
  --color-border:        #e2e8f0;
  --color-text:          #0f172a;
  --color-text-muted:    #64748b;
  --color-accent:        #2563eb;
  --color-accent-subtle: #eff6ff;
  --color-accent-text:   #1d4ed8;
  --color-danger:        #dc2626;
  --color-success-bg:    #f0fdf4;
  --color-success-text:  #166534;
  --color-success-border:#bbf7d0;
  --color-error-bg:      #fef2f2;
  --color-error-text:    #991b1b;
  --color-error-border:  #fecaca;

  --radius-sm:  4px;
  --radius-md:  6px;
  --radius-lg:  8px;
  --radius-xl:  10px;

  --shadow-sm:  0 1px 3px rgba(0,0,0,.06);
  --shadow-md:  0 4px 16px rgba(0,0,0,.10);
  --shadow-lg:  0 8px 32px rgba(0,0,0,.16);

  --nav-top-height:  56px;
  --nav-side-width: 220px;
}

/* ─── Reset ──────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; font-size: 15px;
       background: var(--color-bg); color: var(--color-text); }
a { color: var(--color-accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ─── Login ──────────────────────────────────────────────────────────────── */
.login-page { display: flex; align-items: center; justify-content: center;
              min-height: 100vh; }
.login-box { background: var(--color-surface); padding: 2.5rem;
             border-radius: var(--radius-xl); box-shadow: var(--shadow-md); width: 340px; }
.login-box h1 { font-size: 1.5rem; margin-bottom: 1.5rem; text-align: center; }
.login-box label { display: block; font-weight: 600; margin-bottom: 4px; font-size: 13px; }
.login-box input { width: 100%; padding: 9px 12px; border: 1px solid var(--color-border);
                   border-radius: var(--radius-md); margin-bottom: 1rem; font-size: 14px; }
.login-box button { width: 100%; padding: 10px; background: var(--color-accent);
                    color: #fff; border: none; border-radius: var(--radius-md);
                    font-size: 14px; cursor: pointer; font-weight: 600; }
.login-box button:hover { background: var(--color-accent-text); }
.form-error { color: var(--color-danger); margin-bottom: 1rem; font-size: 13px;
              background: var(--color-error-bg); padding: 8px; border-radius: var(--radius-sm); }

/* ─── App shell ──────────────────────────────────────────────────────────── */
.app-layout { display: flex; flex-direction: column; min-height: 100vh; }

/* Top bar */
.top-bar { position: fixed; top: 0; left: 0; right: 0; height: var(--nav-top-height);
           background: var(--color-surface); border-bottom: 1px solid var(--color-border);
           display: flex; align-items: center; padding: 0 1.25rem;
           z-index: 100; box-shadow: var(--shadow-sm); }
.top-bar-brand { font-size: 1rem; font-weight: 700; color: var(--color-text); flex: 1; }
.top-bar-actions { display: flex; align-items: center; gap: .75rem; }
.top-bar-actions a { font-size: 13px; color: var(--color-text-muted); }
.top-bar-actions a:hover { color: var(--color-text); text-decoration: none; }
.logout-btn { color: var(--color-text-muted); font-size: 13px; cursor: pointer;
              background: none; border: none; padding: 0; }
.logout-btn:hover { color: var(--color-text); }

/* Sidebar */
.sidebar { position: fixed; top: var(--nav-top-height); left: 0;
           width: var(--nav-side-width); height: calc(100vh - var(--nav-top-height));
           background: var(--color-surface); border-right: 1px solid var(--color-border);
           display: flex; flex-direction: column; padding: .75rem .75rem;
           overflow-y: auto; z-index: 90; }
.sidebar-nav { display: flex; flex-direction: column; gap: 2px; }
.sidebar-link { display: flex; align-items: center; gap: 10px; padding: 8px 10px;
                border-radius: var(--radius-md); color: var(--color-text-muted);
                font-size: 14px; font-weight: 500; transition: background .12s, color .12s;
                text-decoration: none; }
.sidebar-link:hover { background: var(--color-bg); color: var(--color-text);
                      text-decoration: none; }
.sidebar-link.active { background: var(--color-accent-subtle); color: var(--color-accent);
                        font-weight: 600; }
.sidebar-link svg { width: 18px; height: 18px; flex-shrink: 0; }

/* Content area */
.page-body { margin-top: var(--nav-top-height); margin-left: var(--nav-side-width);
             padding: 1.5rem; min-height: calc(100vh - var(--nav-top-height)); }

/* Demo banner */
.demo-banner { background: #fef9c3; border-bottom: 1px solid #fde047;
               text-align: center; padding: 8px; font-size: 13px; font-weight: 500;
               position: fixed; top: var(--nav-top-height); left: 0; right: 0; z-index: 80; }
.demo-banner ~ .page-body { margin-top: calc(var(--nav-top-height) + 36px); }

/* ─── Flash messages ─────────────────────────────────────────────────────── */
.flash { padding: 10px 14px; border-radius: var(--radius-md);
         margin-bottom: 1rem; font-size: 13px; }
.flash.success { background: var(--color-success-bg); color: var(--color-success-text);
                  border: 1px solid var(--color-success-border); }
.flash.error   { background: var(--color-error-bg); color: var(--color-error-text);
                  border: 1px solid var(--color-error-border); }

/* ─── Buttons ────────────────────────────────────────────────────────────── */
.btn { padding: 7px 14px; border: none; border-radius: var(--radius-md); font-size: 13px;
       cursor: pointer; font-weight: 500; transition: opacity .1s; display: inline-flex;
       align-items: center; gap: 5px; }
.btn-primary   { background: var(--color-accent); color: #fff; }
.btn-secondary { background: var(--color-bg); color: #334155;
                  border: 1px solid var(--color-border); }
.btn-danger    { background: var(--color-danger); color: #fff; }
.btn-sm        { padding: 4px 10px; font-size: 12px; }
.btn:hover     { opacity: .88; }
.btn:disabled  { opacity: .5; cursor: not-allowed; }

/* ─── Toolbar ────────────────────────────────────────────────────────────── */
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 1rem; flex-wrap: wrap; }
.toolbar select, .toolbar input[type="text"], .toolbar input[type="search"] {
  padding: 7px 10px; border: 1px solid var(--color-border);
  border-radius: var(--radius-md); font-size: 13px; background: var(--color-surface); }

/* ─── Tables ─────────────────────────────────────────────────────────────── */
table { width: 100%; border-collapse: collapse; background: var(--color-surface);
        border-radius: var(--radius-lg); overflow: hidden; box-shadow: var(--shadow-sm); }
thead { background: #f8fafc; }
th { text-align: left; padding: 10px 14px; font-size: 11px; font-weight: 600;
     color: var(--color-text-muted); text-transform: uppercase; letter-spacing: .5px;
     border-bottom: 1px solid var(--color-border); }
td { padding: 11px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }
tr.expired td  { background: #fef2f2; }
tr.expiring td { background: #fff7ed; }

/* ─── Modal ──────────────────────────────────────────────────────────────── */
#modal-container dialog { border: none; border-radius: var(--radius-xl); padding: 0;
                           box-shadow: var(--shadow-lg); max-width: 600px; width: 95%;
                           max-height: 90vh; overflow-y: auto; }
#modal-container dialog::backdrop { background: rgba(0,0,0,.4); }
.dialog-header { padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--color-border);
                 display: flex; justify-content: space-between; align-items: center;
                 position: sticky; top: 0; background: var(--color-surface); z-index: 1; }
.dialog-header h2 { font-size: 1.05rem; font-weight: 600; }
.dialog-body   { padding: 1.5rem; }
.dialog-footer { padding: 1rem 1.5rem; border-top: 1px solid var(--color-border);
                 display: flex; justify-content: flex-end; gap: 8px;
                 position: sticky; bottom: 0; background: var(--color-surface); }

/* ─── Forms ──────────────────────────────────────────────────────────────── */
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-weight: 600; margin-bottom: 4px; font-size: 13px;
                    color: var(--color-text); }
.form-group input, .form-group select, .form-group textarea {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border);
  border-radius: var(--radius-md); font-size: 13px; background: var(--color-surface);
  color: var(--color-text); transition: border-color .15s; }
.form-group input:focus, .form-group select:focus, .form-group textarea:focus {
  outline: none; border-color: var(--color-accent); }
.form-group textarea { min-height: 120px; resize: vertical; }
.form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }

/* ─── Tags ───────────────────────────────────────────────────────────────── */
.tag { display: inline-block; padding: 2px 7px; background: var(--color-accent-subtle);
       color: var(--color-accent-text); border-radius: var(--radius-sm);
       font-size: 11px; font-weight: 500; }

/* ─── Recipe layout ──────────────────────────────────────────────────────── */
.recipes-page { display: grid; grid-template-columns: 300px 1fr; gap: 1.25rem;
                height: calc(100vh - var(--nav-top-height) - 3rem); }

/* List panel */
.recipe-list-panel { background: var(--color-surface); border-radius: var(--radius-lg);
                     box-shadow: var(--shadow-sm); display: flex; flex-direction: column;
                     overflow: hidden; }
.recipe-list-search { padding: .75rem; border-bottom: 1px solid var(--color-border); }
.recipe-list-search input { width: 100%; padding: 8px 10px;
                              border: 1px solid var(--color-border);
                              border-radius: var(--radius-md); font-size: 13px; }
.recipe-list-actions { padding: .5rem .75rem; border-bottom: 1px solid var(--color-border);
                        display: flex; gap: 6px; }
.recipe-list-scroll { overflow-y: auto; flex: 1; }
.recipe-list-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px;
                     border-bottom: 1px solid #f8fafc; cursor: pointer;
                     transition: background .1s; }
.recipe-list-item:hover { background: var(--color-bg); }
.recipe-list-item.active { background: var(--color-accent-subtle);
                             border-left: 3px solid var(--color-accent); }
.recipe-list-thumb { width: 40px; height: 40px; border-radius: var(--radius-sm);
                      object-fit: cover; flex-shrink: 0; background: var(--color-bg);
                      display: flex; align-items: center; justify-content: center;
                      color: var(--color-text-muted); font-size: 18px;
                      border: 1px solid var(--color-border); overflow: hidden; }
.recipe-list-thumb img { width: 100%; height: 100%; object-fit: cover; }
.recipe-list-info { flex: 1; min-width: 0; }
.recipe-list-name { font-size: 13px; font-weight: 600; white-space: nowrap;
                     overflow: hidden; text-overflow: ellipsis; }
.recipe-list-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 3px; }

/* Detail panel */
.recipe-detail-panel { background: var(--color-surface); border-radius: var(--radius-lg);
                        box-shadow: var(--shadow-sm); overflow-y: auto; padding: 1.5rem; }
.recipe-detail-empty { display: flex; align-items: center; justify-content: center;
                        height: 100%; color: var(--color-text-muted); }

/* Detail header */
.recipe-detail-header { display: flex; align-items: flex-start;
                          justify-content: space-between; gap: 1rem; margin-bottom: .75rem; }
.recipe-detail-title { font-size: 1.3rem; font-weight: 700; line-height: 1.3; }
.recipe-detail-actions { display: flex; gap: .5rem; flex-shrink: 0; flex-wrap: wrap; }

/* Meta strip */
.recipe-meta { display: flex; gap: 1.25rem; flex-wrap: wrap; font-size: 13px;
               color: var(--color-text-muted); margin-bottom: .75rem; }
.recipe-meta strong { color: var(--color-text); }

.recipe-tags { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: .75rem; }

/* Three-zone layout */
.recipe-body { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem;
               margin-top: 1rem; }
.recipe-photo { width: 100%; aspect-ratio: 4/3; border-radius: var(--radius-lg);
                object-fit: cover; }
.recipe-photo-placeholder { width: 100%; aspect-ratio: 4/3; border-radius: var(--radius-lg);
                              border: 2px dashed var(--color-border);
                              display: flex; flex-direction: column;
                              align-items: center; justify-content: center;
                              color: var(--color-text-muted); gap: 8px;
                              background: var(--color-bg); }
.recipe-photo-placeholder svg { width: 36px; height: 36px; opacity: .4; }
.recipe-ingredients { }
.recipe-ingredients h3 { font-size: 13px; font-weight: 700; text-transform: uppercase;
                           letter-spacing: .5px; color: var(--color-text-muted);
                           margin-bottom: .5rem; }
.ingredient-list { list-style: none; }
.ingredient-list li { padding: 5px 0; border-bottom: 1px solid #f8fafc; font-size: 14px; }
.ingredient-list li:last-child { border-bottom: none; }

.recipe-instructions { grid-column: 1 / -1; }
.recipe-instructions h3 { font-size: 13px; font-weight: 700; text-transform: uppercase;
                            letter-spacing: .5px; color: var(--color-text-muted);
                            margin-bottom: .75rem; }
.recipe-instructions-text { font-size: 14px; line-height: 1.75; white-space: pre-wrap;
                              color: var(--color-text); }

/* Add recipe dropdown */
.add-recipe-dropdown { position: relative; display: inline-block; }
.add-recipe-menu { position: absolute; top: calc(100% + 4px); left: 0;
                   background: var(--color-surface); border: 1px solid var(--color-border);
                   border-radius: var(--radius-lg); box-shadow: var(--shadow-md);
                   min-width: 170px; z-index: 50; display: none; }
.add-recipe-menu.open { display: block; }
.add-recipe-menu button { display: block; width: 100%; text-align: left;
                           padding: 9px 14px; background: none; border: none;
                           font-size: 13px; cursor: pointer; color: var(--color-text); }
.add-recipe-menu button:hover { background: var(--color-bg); }

/* ─── Meal grid ──────────────────────────────────────────────────────────── */
.meal-grid { display: grid; grid-template-columns: 80px repeat(7, 1fr); gap: 4px; }
.meal-grid-header { font-weight: 600; text-align: center; padding: 8px 4px;
                     font-size: 12px; color: var(--color-text-muted); }
.meal-grid-header.today { color: var(--color-accent); }
.meal-grid-header.today::after { content: ''; display: block; width: 6px; height: 6px;
                                   background: var(--color-accent); border-radius: 50%;
                                   margin: 2px auto 0; }
.meal-slot-label { font-size: 12px; font-weight: 600; color: var(--color-text-muted);
                    display: flex; align-items: center; }
.meal-cell { background: var(--color-surface); border-radius: var(--radius-md);
              min-height: 72px; padding: 8px; border: 1px solid var(--color-border);
              cursor: pointer; transition: border-color .15s; }
.meal-cell:hover { border-color: var(--color-accent); }
.meal-cell.filled { background: var(--color-accent-subtle); border-color: #bfdbfe; }
.meal-cell-name { font-size: 12px; font-weight: 500; }
.meal-cell-servings { font-size: 11px; color: var(--color-text-muted); }

/* ─── Shopping list ──────────────────────────────────────────────────────── */
.shopping-store { margin-bottom: 1.5rem; }
.shopping-store-header { background: var(--color-bg); border: 1px solid var(--color-border);
                           border-radius: var(--radius-md); padding: 7px 12px;
                           font-size: 12px; font-weight: 700; margin-bottom: 8px;
                           color: var(--color-text-muted); text-transform: uppercase;
                           letter-spacing: .5px; }
.shopping-item { display: flex; align-items: center; gap: 10px; padding: 7px 4px;
                  border-bottom: 1px solid #f1f5f9; }
.shopping-item:last-child { border-bottom: none; }
.shopping-item input[type="checkbox"] { width: 16px; height: 16px; }
.shopping-item label { flex: 1; font-size: 13px; }

/* ─── Help page ──────────────────────────────────────────────────────────── */
.help-page { max-width: 860px; }
.help-page h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 1.25rem; }
.help-page h2 { font-size: 1.15rem; font-weight: 700; margin-top: 2rem; margin-bottom: .5rem;
                 border-bottom: 2px solid var(--color-border); padding-bottom: .35rem;
                 color: var(--color-accent-text); }
.help-page h3 { font-size: 1rem; font-weight: 700; margin-top: 1.25rem; margin-bottom: .25rem; }
.help-page p { margin-bottom: .75rem; line-height: 1.65; }
.help-page ul, .help-page ol { margin: .5rem 0 .75rem 1.5rem; line-height: 1.65; }
.help-page li { margin-bottom: .25rem; }
.help-page table { width: 100%; border-collapse: collapse; margin: 1rem 0 1.25rem; font-size: 13px; }
.help-page th { background: #f1f5f9; font-weight: 600; text-align: left;
                 padding: 8px 10px; border: 1px solid var(--color-border); }
.help-page td { padding: 7px 10px; border: 1px solid var(--color-border); vertical-align: top; }
.help-page code { background: var(--color-bg); padding: 1px 5px; border-radius: var(--radius-sm);
                   font-size: .85em; font-family: monospace; }
.help-page hr { border: none; border-top: 1px solid var(--color-border); margin: 1.5rem 0; }

/* ─── HTMX loading ───────────────────────────────────────────────────────── */
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline; }
.htmx-request.htmx-indicator { display: inline; }
.spinner { display: inline-block; width: 16px; height: 16px;
           border: 2px solid var(--color-border); border-top-color: var(--color-accent);
           border-radius: 50%; animation: spin .6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── Mobile ─────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .sidebar { display: none; }
  .page-body { margin-left: 0; padding: 1rem; padding-bottom: 72px; }

  /* Bottom tab bar */
  .bottom-tab-bar { display: flex; position: fixed; bottom: 0; left: 0; right: 0;
                     height: 60px; background: var(--color-surface);
                     border-top: 1px solid var(--color-border); z-index: 100; }
  .bottom-tab-bar a { flex: 1; display: flex; flex-direction: column; align-items: center;
                       justify-content: center; gap: 2px; color: var(--color-text-muted);
                       font-size: 10px; font-weight: 500; text-decoration: none; }
  .bottom-tab-bar a.active { color: var(--color-accent); }
  .bottom-tab-bar svg { width: 22px; height: 22px; }

  /* Recipes: mobile single-pane */
  .recipes-page { grid-template-columns: 1fr; height: auto; }
  .recipe-detail-panel { display: none; }
  .recipes-page.detail-open .recipe-list-panel { display: none; }
  .recipes-page.detail-open .recipe-detail-panel { display: block; }

  /* Recipe body stacks on mobile */
  .recipe-body { grid-template-columns: 1fr; }
}

@media (min-width: 769px) {
  .bottom-tab-bar { display: none; }
}
```

**Step 2: Run the app and visually check**

```bash
uvicorn app.main:app --reload --port 8080
```

Open `http://localhost:8080/pantry` — the page will look broken until Task 6 updates `base.html`. That's fine; continue.

**Step 3: Commit**

```bash
git add app/static/style.css
git commit -m "feat: rewrite CSS with design system and new layout tokens"
```

---

## Task 6: Rewrite base.html — top bar + sidebar nav

**Files:**
- Modify: `app/templates/base.html`

SVG icons are inlined (no external dependency). Each nav item uses a simple path.

**Step 1: Replace base.html entirely**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Meal Planner{% endblock %}</title>
  <link rel="stylesheet" href="/static/style.css">
  <script src="/static/htmx.min.js" defer></script>
</head>
<body class="app-layout">

{% if demo %}
<div class="demo-banner">
  Demo mode — browsing is enabled, but changes are disabled.
</div>
{% endif %}

<!-- Top bar -->
<header class="top-bar">
  <span class="top-bar-brand">Meal Planner</span>
  <div class="top-bar-actions">
    <a href="/help">Help</a>
    {% if not demo %}
    <form method="post" action="/logout" style="display:inline">
      <button type="submit" class="logout-btn">Sign out</button>
    </form>
    {% endif %}
  </div>
</header>

<!-- Sidebar (desktop) -->
<nav class="sidebar">
  <div class="sidebar-nav">
    <a href="{{ '/demo' if demo else '' }}/pantry"
       class="sidebar-link {{ 'active' if active_tab == 'pantry' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <polyline points="9 22 9 12 15 12 15 22"/>
      </svg>
      Pantry
    </a>
    <a href="{{ '/demo' if demo else '' }}/recipes"
       class="sidebar-link {{ 'active' if active_tab == 'recipes' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
      </svg>
      Recipes
    </a>
    <a href="{{ '/demo' if demo else '' }}/meal-plan"
       class="sidebar-link {{ 'active' if active_tab == 'meal_plan' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
      Meal Plan
    </a>
    <a href="{{ '/demo' if demo else '' }}/shopping"
       class="sidebar-link {{ 'active' if active_tab == 'shopping' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
        <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
      </svg>
      Shopping
    </a>
    <a href="{{ '/demo' if demo else '' }}/stores"
       class="sidebar-link {{ 'active' if active_tab == 'stores' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
        <path d="M9 22V12h6v10"/>
      </svg>
      Stores
    </a>
    {% if not demo %}
    <a href="/settings"
       class="sidebar-link {{ 'active' if active_tab == 'settings' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
      Settings
    </a>
    {% endif %}
  </div>
</nav>

<!-- Bottom tab bar (mobile only) -->
<nav class="bottom-tab-bar">
  <a href="{{ '/demo' if demo else '' }}/pantry"
     class="{{ 'active' if active_tab == 'pantry' }}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      <polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
    Pantry
  </a>
  <a href="{{ '/demo' if demo else '' }}/recipes"
     class="{{ 'active' if active_tab == 'recipes' }}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
    </svg>
    Recipes
  </a>
  <a href="{{ '/demo' if demo else '' }}/meal-plan"
     class="{{ 'active' if active_tab == 'meal_plan' }}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
      <line x1="16" y1="2" x2="16" y2="6"/>
      <line x1="8" y1="2" x2="8" y2="6"/>
      <line x1="3" y1="10" x2="21" y2="10"/>
    </svg>
    Meal Plan
  </a>
  <a href="{{ '/demo' if demo else '' }}/shopping"
     class="{{ 'active' if active_tab == 'shopping' }}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
    </svg>
    Shopping
  </a>
  <a href="{{ '/demo' if demo else '' }}/stores"
     class="{{ 'active' if active_tab == 'stores' }}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
      <path d="M9 22V12h6v10"/>
    </svg>
    Stores
  </a>
</nav>

<!-- Page content -->
<main class="page-body">
  <div id="flash-area">
  {% if flash_message %}
    <div class="flash {{ flash_type | default('success') }}">{{ flash_message }}</div>
  {% endif %}
  </div>
  {% block content %}{% endblock %}
</main>

<div id="modal-container"></div>

<script>
// Open dialog after HTMX loads it into modal-container
document.addEventListener('htmx:afterSwap', function(e) {
  if (e.target.id === 'modal-container') {
    const dialog = e.target.querySelector('dialog');
    if (dialog && !dialog.open) dialog.showModal();
  }
});
// Close modal when clicking the backdrop
document.addEventListener('click', function(e) {
  const dialog = document.querySelector('#modal-container dialog');
  if (dialog && e.target === dialog) {
    dialog.close();
    dialog.remove();
  }
});
// Add recipe dropdown toggle
document.addEventListener('click', function(e) {
  const btn = e.target.closest('[data-dropdown-toggle]');
  const menu = document.querySelector('.add-recipe-menu');
  if (!menu) return;
  if (btn) {
    menu.classList.toggle('open');
    e.stopPropagation();
  } else {
    menu.classList.remove('open');
  }
});
</script>

</body>
</html>
```

**Step 2: Run tests**

```bash
pytest tests/ -v
```
Expected: all pass (nav change doesn't affect route logic)

**Step 3: Commit**

```bash
git add app/templates/base.html
git commit -m "feat: new base layout — top bar + sidebar + mobile bottom tab bar"
```

---

## Task 7: Update recipes.html and partials for new layout

**Files:**
- Modify: `app/templates/recipes.html`
- Modify: `app/templates/partials/recipe_list.html`
- Modify: `app/templates/partials/recipe_detail.html`

**Step 1: Rewrite recipes.html**

```html
{% extends "base.html" %}
{% block title %}Recipes — Meal Planner{% endblock %}
{% block content %}

<div class="recipes-page" id="recipes-page">

  <!-- ── Left: recipe list ── -->
  <div class="recipe-list-panel">
    <div class="recipe-list-search">
      <input type="search" name="q" placeholder="Search recipes…"
             hx-get="/recipes/list"
             hx-target="#recipe-list"
             hx-trigger="input changed delay:300ms, search"
             hx-include="this">
    </div>

    {% if not demo %}
    <div class="recipe-list-actions">
      <div class="add-recipe-dropdown">
        <button class="btn btn-primary btn-sm" data-dropdown-toggle>+ Add ▾</button>
        <div class="add-recipe-menu">
          <button hx-get="/recipes/add" hx-target="#modal-container">Add Manually</button>
          <button hx-get="/recipes/ai/paste" hx-target="#modal-container">Paste Text</button>
          <button hx-get="/recipes/ai/url" hx-target="#modal-container">From URL</button>
          <button hx-get="/recipes/ai/generate" hx-target="#modal-container">AI Generate</button>
        </div>
      </div>
      <span class="htmx-indicator"><span class="spinner"></span></span>
    </div>
    {% endif %}

    <div id="recipe-list" class="recipe-list-scroll">
      {% include "partials/recipe_list.html" %}
    </div>
  </div>

  <!-- ── Right: recipe detail ── -->
  <div class="recipe-detail-panel" id="recipe-detail">
    <div class="recipe-detail-empty">Select a recipe to view details.</div>
  </div>

</div>

<script>
// Mobile: toggle pane visibility when a recipe is selected
document.addEventListener('htmx:afterSwap', function(e) {
  if (e.target.id === 'recipe-detail') {
    document.getElementById('recipes-page').classList.add('detail-open');
  }
});
</script>

{% endblock %}
```

**Step 2: Rewrite partials/recipe_list.html**

```html
{% if recipes %}
{% for recipe in recipes %}
<div class="recipe-list-item {{ 'active' if selected_id and selected_id == recipe.id }}"
     hx-get="/recipes/{{ recipe.id }}"
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

**Step 3: Rewrite partials/recipe_detail.html**

```html
<div class="recipe-detail">

  <!-- Header -->
  <div class="recipe-detail-header">
    <h1 class="recipe-detail-title">{{ recipe.name }}</h1>
    {% if not demo %}
    <div class="recipe-detail-actions">
      <button class="btn btn-secondary btn-sm"
              hx-get="/recipes/{{ recipe.id }}/edit"
              hx-target="#modal-container">Edit</button>
      <button class="btn btn-secondary btn-sm"
              hx-get="/recipes/{{ recipe.id }}/ai/modify"
              hx-target="#modal-container">Modify with AI</button>
      <button class="btn btn-danger btn-sm"
              hx-delete="/recipes/{{ recipe.id }}"
              hx-confirm="Delete {{ recipe.name }}?"
              hx-target="body"
              hx-push-url="/recipes">Delete</button>
    </div>
    {% endif %}
  </div>

  <!-- Meta strip -->
  <div class="recipe-meta">
    {% if recipe.servings %}<span><strong>Servings:</strong> {{ recipe.servings }}</span>{% endif %}
    {% if recipe.prep_time %}<span><strong>Prep:</strong> {{ recipe.prep_time }}</span>{% endif %}
    {% if recipe.cook_time %}<span><strong>Cook:</strong> {{ recipe.cook_time }}</span>{% endif %}
    {% if recipe.rating %}<span><strong>Rating:</strong> {{ recipe.rating }}/5</span>{% endif %}
    {% if recipe.source_url %}
    <span><a href="{{ recipe.source_url }}" target="_blank" rel="noopener">Source ↗</a></span>
    {% endif %}
  </div>

  {% if recipe.tags %}
  <div class="recipe-tags">
    {% for tag in recipe.tags.split(',') %}
    <span class="tag">{{ tag.strip() }}</span>
    {% endfor %}
  </div>
  {% endif %}

  {% if recipe.description %}
  <p style="font-size:14px;color:var(--color-text-muted);margin-bottom:.5rem">{{ recipe.description }}</p>
  {% endif %}

  <!-- Three-zone body -->
  <div class="recipe-body">

    <!-- Top-left: ingredients -->
    <div class="recipe-ingredients">
      <h3>Ingredients</h3>
      {% if recipe.ingredients %}
      <ul class="ingredient-list">
        {% for ing in recipe.ingredients %}
        <li>
          {% if ing.quantity %}{{ ing.quantity|round(2) }}{% endif %}
          {% if ing.unit %}{{ ing.unit }}{% endif %}
          {{ ing.name }}
        </li>
        {% endfor %}
      </ul>
      {% else %}
      <p style="color:var(--color-text-muted);font-size:13px">No ingredients listed.</p>
      {% endif %}
    </div>

    <!-- Top-right: photo -->
    <div>
      {% if recipe.photo_path %}
      <img src="{{ recipe.photo_path }}" alt="{{ recipe.name }}" class="recipe-photo">
      {% else %}
      <div class="recipe-photo-placeholder">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
          <circle cx="12" cy="13" r="4"/>
        </svg>
        <span style="font-size:12px">No photo</span>
      </div>
      {% endif %}
    </div>

    <!-- Full-width: instructions -->
    {% if recipe.instructions %}
    <div class="recipe-instructions">
      <h3>Instructions</h3>
      <div class="recipe-instructions-text">{{ recipe.instructions }}</div>
    </div>
    {% endif %}

  </div>

  <!-- Mobile back button -->
  <div style="margin-top:1.5rem;display:none" class="mobile-back-btn">
    <button class="btn btn-secondary btn-sm"
            onclick="document.getElementById('recipes-page').classList.remove('detail-open')">
      ← Back to recipes
    </button>
  </div>

</div>

<style>
@media (max-width: 768px) {
  .mobile-back-btn { display: block !important; }
}
</style>
```

**Step 4: Run tests**

```bash
pytest tests/ -v
```

**Step 5: Commit**

```bash
git add app/templates/recipes.html app/templates/partials/recipe_list.html app/templates/partials/recipe_detail.html
git commit -m "feat: new recipe layout — thumbnail list, three-zone detail, mobile nav"
```

---

## Task 8: Polish Pantry, Meal Plan, and Shopping templates

**Files:**
- Modify: `app/templates/pantry.html`
- Modify: `app/templates/meal_plan.html`
- Modify: `app/templates/shopping.html`

Read each template fully before editing to understand current structure.

**Step 1: Read pantry.html**

```bash
# Read app/templates/pantry.html
```

Update the outer wrapper: replace `<div class="tab-content">` style wrappers (if any inside the block) with plain `<div>`. The `page-body` class is now on `<main>` in base.html, so the inner content just needs to flow normally.

Also update the shopping list store header in `partials/shopping_list.html` if it exists: change any `<h3>` store header to use the new `<div class="shopping-store-header">` element.

**Step 2: Update meal plan template**

Read `app/templates/meal_plan.html`. Find where day column headers are rendered in `partials/meal_grid.html`. Add `today` class to the header cell for today's date:

In `app/templates/partials/meal_grid.html`, find the day header cells. They will reference the date. Add:
```html
class="meal-grid-header {{ 'today' if day == today }}"
```

Make sure `today` is passed from the meal_plan router context (it likely already is; if not, add `"today": date.today().isoformat()` to the template context in `app/routers/meal_plan.py`).

**Step 3: Update shopping list partial**

Read `app/templates/partials/shopping_list.html`. Find the store group heading and replace:
```html
<h3>{{ store }}</h3>
```
with:
```html
<div class="shopping-store-header">{{ store }}</div>
```

**Step 4: Run tests**

```bash
pytest tests/ -v
```

**Step 5: Commit**

```bash
git add app/templates/pantry.html app/templates/meal_plan.html app/templates/shopping.html app/templates/partials/
git commit -m "feat: apply new design system to pantry, meal plan, shopping tabs"
```

---

## Task 9: Final verification and push

**Step 1: Run full test suite**

```bash
pytest tests/ -v
```
Expected: all tests pass

**Step 2: Run app locally and check each page**

```bash
uvicorn app.main:app --reload --port 8080
```

Check in browser:
- [ ] `/pantry` — sidebar active, full-width table, correct colours
- [ ] `/recipes` — thumbnail list, three-zone detail, Add dropdown works
- [ ] `/recipes` on mobile viewport (DevTools) — bottom tab bar visible, single-pane + back button works
- [ ] `/meal-plan` — grid renders, today column highlighted
- [ ] `/shopping` — store headers have grey band
- [ ] `/settings` — inherits new card/form styles
- [ ] `/help` — readable, inherits new styles
- [ ] Photo upload: add a recipe, upload a photo, verify it appears in detail view and list thumbnail
- [ ] URL import: import a recipe from a URL with og:image, verify photo auto-fills

**Step 3: Push**

```bash
git push origin clean-main:main
```
