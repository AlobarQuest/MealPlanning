# Web Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the Meal Planner PySide6 desktop app to a FastAPI + HTMX web app accessible locally and remotely via Docker, preserving all business logic unchanged.

**Architecture:** Keep `meal_planner/db/` and `meal_planner/core/` layers intact — they become the service layer. Add a new `app/` directory of FastAPI routers + Jinja2 templates that call `core/` functions directly. Single-password auth via middleware + signed cookie. Read-only `/demo/*` routes backed by a seeded fake SQLite DB, using a ContextVar to swap DB paths per-request.

**Tech Stack:** FastAPI 0.115+, Uvicorn, Jinja2, HTMX 2.x, itsdangerous, python-multipart, python-dotenv, pytest + httpx (TestClient)

---

## Task 1: Update requirements.txt and make DB path configurable

**Files:**
- Modify: `requirements.txt`
- Modify: `meal_planner/db/database.py`

**Step 1: Replace requirements.txt contents**

```
# Web framework
fastapi>=0.115.0
uvicorn>=0.30.0
jinja2>=3.1.0
python-multipart>=0.0.9
itsdangerous>=2.2.0
python-dotenv>=1.0.0

# AI + HTTP (existing)
anthropic>=0.25.0
httpx>=0.27.0

# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

(Remove `PySide6>=6.6.0` entirely.)

**Step 2: Update `get_db_path()` in `meal_planner/db/database.py`**

Replace the current `get_db_path()` function (lines 12–16) with:

```python
import os
from contextvars import ContextVar

_db_path_override: ContextVar["Path | None"] = ContextVar("_db_path_override", default=None)


def get_db_path() -> Path:
    """Return the active DB path.

    Priority order:
    1. ContextVar override (used by demo routes per-request)
    2. DATABASE_URL environment variable (used by Docker / local dev)
    3. Default ~/.meal_planner/meal_planner.db (desktop fallback)
    """
    override = _db_path_override.get()
    if override is not None:
        return override
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        p = Path(env_url)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    db_dir = Path.home() / ".meal_planner"
    db_dir.mkdir(exist_ok=True)
    return db_dir / "meal_planner.db"
```

Leave `get_connection()` and `init_db()` exactly as they are — they already call `get_db_path()` internally.

**Step 3: Install and verify**

```bash
pip install -r requirements.txt
python -c "from meal_planner.db.database import get_connection; c = get_connection(); c.close(); print('DB OK')"
```

Expected output: `DB OK`

**Step 4: Commit**

```bash
git add requirements.txt meal_planner/db/database.py
git commit -m "feat: update deps for web, make DB path env+contextvar configurable"
```

---

## Task 2: Scaffold app/ directory and FastAPI skeleton

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/dependencies.py`
- Create: `app/routers/__init__.py`
- Create: `app/routers/auth.py` (stub)
- Create: `app/routers/pantry.py` (stub)
- Create: `app/routers/recipes.py` (stub)
- Create: `app/routers/meal_plan.py` (stub)
- Create: `app/routers/shopping.py` (stub)
- Create: `app/routers/stores.py` (stub)
- Create: `app/routers/settings.py` (stub)
- Create: `app/templates/` (dir)
- Create: `app/templates/partials/` (dir)
- Create: `app/static/` (dir)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.env` (local dev only, git-ignored)
- Create: `.env.example`

**Step 1: Create directories**

```bash
mkdir -p app/routers app/templates/partials app/static tests
touch app/__init__.py app/routers/__init__.py tests/__init__.py
```

**Step 2: Create `app/dependencies.py`**

```python
import os
from pathlib import Path
from itsdangerous import URLSafeTimedSerializer
from fastapi import Request
from fastapi.responses import RedirectResponse

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
SESSION_COOKIE = "mp_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

_signer = URLSafeTimedSerializer(SECRET_KEY)


def create_session_token() -> str:
    return _signer.dumps("ok")


def verify_session_token(token: str) -> bool:
    try:
        _signer.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except Exception:
        return False


# Paths that don't require auth
_PUBLIC_PREFIXES = ("/login", "/static", "/demo")


def is_public(path: str) -> bool:
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)
```

**Step 3: Create `app/main.py`**

```python
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from meal_planner.db.database import init_db, _db_path_override
from app.dependencies import verify_session_token, is_public, SESSION_COOKIE
from app.routers import auth, pantry, recipes, meal_plan, shopping, stores, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize main DB
    init_db()
    # Initialize demo DB if DEMO_DB_URL is set
    demo_url = os.environ.get("DEMO_DB_URL")
    if demo_url:
        from pathlib import Path
        token = _db_path_override.set(Path(demo_url))
        try:
            init_db()
            from demo.seed import seed_if_empty
            seed_if_empty()
        finally:
            _db_path_override.reset(token)
    yield


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not is_public(request.url.path):
        token = request.cookies.get(SESSION_COOKIE)
        if not token or not verify_session_token(token):
            return RedirectResponse(url="/login", status_code=302)
    return await call_next(request)


app.include_router(auth.router)
app.include_router(pantry.router)
app.include_router(recipes.router)
app.include_router(meal_plan.router)
app.include_router(shopping.router)
app.include_router(stores.router)
app.include_router(settings.router)
```

**Step 4: Create stub routers (same pattern for all 7)**

`app/routers/auth.py`:
```python
from fastapi import APIRouter
router = APIRouter(tags=["auth"])
```

Repeat for `pantry.py`, `recipes.py`, `meal_plan.py`, `shopping.py`, `stores.py`, `settings.py` — just the APIRouter line, different tag name.

**Step 5: Create `tests/conftest.py`**

```python
import os
import tempfile
import pytest
from pathlib import Path

# Set env vars BEFORE importing the app
@pytest.fixture(scope="session", autouse=True)
def set_test_env(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("data") / "test.db"
    os.environ["DATABASE_URL"] = str(db_file)
    os.environ["APP_PASSWORD"] = "testpass"
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["DEMO_DB_URL"] = str(tmp_path_factory.mktemp("demo") / "demo.db")


@pytest.fixture(scope="session")
def client(set_test_env):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def authed_client(client):
    client.post("/login", data={"password": "testpass"}, follow_redirects=False)
    return client
```

**Step 6: Create `.env.example`**

```
APP_PASSWORD=changeme
SECRET_KEY=generate-a-long-random-string
DATABASE_URL=/data/meal_planner.db
DEMO_DB_URL=/data/demo.db
CLAUDE_API_KEY=sk-ant-...
```

**Step 7: Create `.env` for local dev (add to .gitignore)**

```
APP_PASSWORD=localpass
SECRET_KEY=dev-only-not-secret
DATABASE_URL=
DEMO_DB_URL=
CLAUDE_API_KEY=sk-ant-...
```

Add `.env` to `.gitignore` if not already present.

**Step 8: Verify app starts**

```bash
uvicorn app.main:app --reload --port 8080
```

Expected: Uvicorn starts with no import errors. `http://localhost:8080/docs` is accessible.

**Step 9: Commit**

```bash
git add app/ tests/ .env.example .gitignore
git commit -m "feat: scaffold FastAPI app directory, dependencies, test fixtures"
```

---

## Task 3: Auth — login, logout, session

**Files:**
- Modify: `app/routers/auth.py`
- Create: `app/templates/login.html`
- Create: `app/static/style.css` (minimal — expand later)
- Create: `app/static/htmx.min.js` (download)
- Create: `tests/test_auth.py`

**Step 1: Download HTMX**

```bash
curl -o app/static/htmx.min.js https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js
```

**Step 2: Write failing tests**

`tests/test_auth.py`:
```python
def test_login_page_returns_200(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "password" in resp.text.lower()


def test_login_wrong_password_returns_error(client):
    resp = client.post("/login", data={"password": "wrong"}, follow_redirects=False)
    assert resp.status_code == 200
    assert "invalid" in resp.text.lower()


def test_login_correct_password_sets_cookie_and_redirects(client):
    resp = client.post("/login", data={"password": "testpass"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/pantry"
    assert "mp_session" in resp.cookies


def test_protected_route_redirects_unauthenticated(client):
    # Use a fresh client with no session cookie
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as fresh:
        resp = fresh.get("/pantry", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]


def test_logout_clears_cookie(authed_client):
    resp = authed_client.post("/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"
```

**Step 3: Run tests — expect failures**

```bash
pytest tests/test_auth.py -v
```

Expected: All fail (routes not implemented yet).

**Step 4: Implement `app/routers/auth.py`**

```python
import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.dependencies import create_session_token, SESSION_COOKIE, SESSION_MAX_AGE

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")

APP_PASSWORD = os.environ.get("APP_PASSWORD", "")


@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/pantry", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password and password == APP_PASSWORD:
        resp = RedirectResponse(url="/pantry", status_code=302)
        resp.set_cookie(
            SESSION_COOKIE,
            create_session_token(),
            httponly=True,
            samesite="lax",
            max_age=SESSION_MAX_AGE,
        )
        return resp
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid password"},
        status_code=200,
    )


@router.post("/logout")
async def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp
```

**Step 5: Create `app/templates/login.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meal Planner — Sign In</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body class="login-page">
  <div class="login-box">
    <h1>🍽 Meal Planner</h1>
    {% if error %}
      <p class="form-error">{{ error }}</p>
    {% endif %}
    <form method="post" action="/login">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" autofocus required>
      <button type="submit">Sign In</button>
    </form>
  </div>
</body>
</html>
```

**Step 6: Create `app/static/style.css` (minimal starter)**

```css
/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; font-size: 14px;
       background: #f0f2f5; color: #1a1a2e; }
a { color: #2563eb; text-decoration: none; }

/* ── Login ── */
.login-page { display: flex; align-items: center; justify-content: center;
              min-height: 100vh; }
.login-box { background: #fff; padding: 2.5rem; border-radius: 10px;
             box-shadow: 0 4px 16px rgba(0,0,0,.1); width: 340px; }
.login-box h1 { font-size: 1.5rem; margin-bottom: 1.5rem; text-align: center; }
.login-box label { display: block; font-weight: 600; margin-bottom: 4px; }
.login-box input { width: 100%; padding: 9px 12px; border: 1px solid #d1d5db;
                   border-radius: 6px; margin-bottom: 1rem; font-size: 14px; }
.login-box button { width: 100%; padding: 10px; background: #2563eb;
                    color: #fff; border: none; border-radius: 6px;
                    font-size: 14px; cursor: pointer; font-weight: 600; }
.login-box button:hover { background: #1d4ed8; }
.form-error { color: #dc2626; margin-bottom: 1rem; font-size: 13px;
              background: #fef2f2; padding: 8px; border-radius: 4px; }

/* ── Layout ── */
.app-layout { display: flex; flex-direction: column; min-height: 100vh; }
nav.tab-bar { background: #1e293b; display: flex; align-items: center;
              padding: 0 1rem; gap: 4px; }
nav.tab-bar a { color: #94a3b8; padding: 14px 18px; font-size: 14px;
                font-weight: 500; border-bottom: 3px solid transparent; }
nav.tab-bar a:hover { color: #e2e8f0; }
nav.tab-bar a.active { color: #fff; border-bottom-color: #2563eb; }
nav.tab-bar .spacer { flex: 1; }
nav.tab-bar .logout-btn { color: #94a3b8; font-size: 13px; cursor: pointer;
                           background: none; border: none; padding: 14px 12px; }
nav.tab-bar .logout-btn:hover { color: #e2e8f0; }
.tab-content { padding: 1.5rem; max-width: 1200px; margin: 0 auto; width: 100%; }

/* ── Demo banner ── */
.demo-banner { background: #fef9c3; border-bottom: 1px solid #fde047;
               text-align: center; padding: 8px; font-size: 13px; font-weight: 500; }

/* ── Flash messages ── */
.flash { padding: 10px 14px; border-radius: 6px; margin-bottom: 1rem; font-size: 13px; }
.flash.success { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.flash.error   { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }

/* ── Toolbar (filters + buttons above tables) ── */
.toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 1rem;
           flex-wrap: wrap; }
.toolbar select, .toolbar input[type="text"] {
  padding: 7px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; }

/* ── Buttons ── */
.btn { padding: 7px 14px; border: none; border-radius: 6px; font-size: 13px;
       cursor: pointer; font-weight: 500; }
.btn-primary   { background: #2563eb; color: #fff; }
.btn-secondary { background: #e2e8f0; color: #334155; }
.btn-danger    { background: #dc2626; color: #fff; }
.btn-sm        { padding: 4px 10px; font-size: 12px; }
.btn:hover     { opacity: 0.9; }
.btn:disabled  { opacity: 0.5; cursor: not-allowed; }

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
thead { background: #f8fafc; }
th { text-align: left; padding: 10px 12px; font-size: 12px; font-weight: 600;
     color: #64748b; text-transform: uppercase; letter-spacing: .5px;
     border-bottom: 1px solid #e2e8f0; }
td { padding: 10px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #f8fafc; }
tr.expired td  { background: #fef2f2; }
tr.expiring td { background: #fff7ed; }

/* ── Modal overlay ── */
#modal-container dialog { border: none; border-radius: 10px; padding: 0;
                           box-shadow: 0 8px 32px rgba(0,0,0,.2);
                           max-width: 560px; width: 100%; }
#modal-container dialog::backdrop { background: rgba(0,0,0,.4); }
.dialog-header { padding: 1.25rem 1.5rem; border-bottom: 1px solid #e2e8f0;
                 display: flex; justify-content: space-between; align-items: center; }
.dialog-header h2 { font-size: 1.1rem; }
.dialog-body   { padding: 1.5rem; }
.dialog-footer { padding: 1rem 1.5rem; border-top: 1px solid #e2e8f0;
                 display: flex; justify-content: flex-end; gap: 8px; }

/* ── Forms ── */
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-weight: 600; margin-bottom: 4px; font-size: 13px; }
.form-group input, .form-group select, .form-group textarea {
  width: 100%; padding: 8px 10px; border: 1px solid #d1d5db;
  border-radius: 6px; font-size: 13px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

/* ── Recipe detail panel ── */
.recipe-layout { display: grid; grid-template-columns: 280px 1fr; gap: 1.5rem;
                 height: calc(100vh - 120px); }
.recipe-list-panel { background: #fff; border-radius: 8px; overflow-y: auto;
                      box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.recipe-detail-panel { background: #fff; border-radius: 8px; overflow-y: auto;
                        padding: 1.5rem; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.recipe-list-item { padding: 12px 16px; border-bottom: 1px solid #f1f5f9;
                     cursor: pointer; }
.recipe-list-item:hover { background: #f8fafc; }
.recipe-list-item.active { background: #eff6ff; border-left: 3px solid #2563eb; }

/* ── Meal plan grid ── */
.meal-grid { display: grid; grid-template-columns: 80px repeat(7, 1fr);
              gap: 4px; }
.meal-grid-header { font-weight: 600; text-align: center; padding: 8px 4px;
                     font-size: 12px; color: #64748b; }
.meal-slot-label { font-size: 12px; font-weight: 600; color: #64748b;
                    display: flex; align-items: center; }
.meal-cell { background: #fff; border-radius: 6px; min-height: 72px;
              padding: 6px; border: 1px solid #e2e8f0; cursor: pointer;
              transition: border-color .15s; }
.meal-cell:hover { border-color: #2563eb; }
.meal-cell.filled { background: #eff6ff; border-color: #bfdbfe; }
.meal-cell-name { font-size: 12px; font-weight: 500; }
.meal-cell-servings { font-size: 11px; color: #64748b; }

/* ── Shopping list ── */
.shopping-store { margin-bottom: 1.5rem; }
.shopping-store h3 { font-size: 14px; font-weight: 700; margin-bottom: 8px;
                      color: #475569; text-transform: uppercase; letter-spacing: .5px; }
.shopping-item { display: flex; align-items: center; gap: 10px;
                  padding: 6px 0; border-bottom: 1px solid #f1f5f9; }
.shopping-item:last-child { border-bottom: none; }
.shopping-item input[type="checkbox"] { width: 16px; height: 16px; }
.shopping-item label { flex: 1; font-size: 13px; }
.shopping-item .cost { font-size: 12px; color: #64748b; }

/* ── HTMX loading indicator ── */
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline; }
.htmx-request.htmx-indicator { display: inline; }
.spinner { display: inline-block; width: 16px; height: 16px;
           border: 2px solid #e2e8f0; border-top-color: #2563eb;
           border-radius: 50%; animation: spin .6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
```

**Step 7: Run tests — expect pass**

```bash
pytest tests/test_auth.py -v
```

Expected: All 5 tests pass.

**Step 8: Manual smoke test**

```bash
uvicorn app.main:app --reload --port 8080
```

Visit `http://localhost:8080` → redirected to `/login`. Enter correct password → redirected to `/pantry` (404 for now, that's fine). `/logout` clears cookie.

**Step 9: Commit**

```bash
git add app/ tests/ app/static/
git commit -m "feat: auth login/logout/session middleware, login page, base styles"
```

---

## Task 4: Base template + nav

**Files:**
- Create: `app/templates/base.html`

**Step 1: Create `app/templates/base.html`**

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
  👁 Demo mode — browsing is enabled, but changes are disabled.
</div>
{% endif %}

<nav class="tab-bar">
  <a href="{{ '/demo' if demo else '' }}/pantry"
     class="{{ 'active' if active_tab == 'pantry' }}">Pantry</a>
  <a href="{{ '/demo' if demo else '' }}/recipes"
     class="{{ 'active' if active_tab == 'recipes' }}">Recipes</a>
  <a href="{{ '/demo' if demo else '' }}/meal-plan"
     class="{{ 'active' if active_tab == 'meal_plan' }}">Meal Plan</a>
  <a href="{{ '/demo' if demo else '' }}/shopping"
     class="{{ 'active' if active_tab == 'shopping' }}">Shopping List</a>
  <a href="{{ '/demo' if demo else '' }}/stores"
     class="{{ 'active' if active_tab == 'stores' }}">Stores</a>
  {% if not demo %}
  <a href="/settings" class="{{ 'active' if active_tab == 'settings' }}">Settings</a>
  {% endif %}
  <span class="spacer"></span>
  {% if not demo %}
  <form method="post" action="/logout" style="display:inline">
    <button type="submit" class="logout-btn">Sign out</button>
  </form>
  {% endif %}
</nav>

<main class="tab-content">
  {% if flash_message %}
    <div class="flash {{ flash_type | default('success') }}">{{ flash_message }}</div>
  {% endif %}
  {% block content %}{% endblock %}
</main>

<div id="modal-container"></div>

<script>
// Close modal when clicking the backdrop
document.addEventListener('click', function(e) {
  const dialog = document.querySelector('#modal-container dialog');
  if (dialog && e.target === dialog) dialog.remove();
});
// Open dialog after HTMX loads it into modal-container
document.addEventListener('htmx:afterSwap', function(e) {
  const dialog = document.querySelector('#modal-container dialog');
  if (dialog && !dialog.open) dialog.showModal();
});
</script>

</body>
</html>
```

**Step 2: Verify by adding a temporary test route**

Add to `app/routers/auth.py` temporarily:
```python
@router.get("/test-base", response_class=HTMLResponse)
async def test_base(request: Request):
    return templates.TemplateResponse("base.html", {
        "request": request, "active_tab": "pantry", "demo": False
    })
```

Visit `http://localhost:8080/test-base` (after auth) — should show nav bar with tabs.

Remove the test route after verifying.

**Step 3: Commit**

```bash
git add app/templates/base.html
git commit -m "feat: base template with nav, modal container, demo banner"
```

---

## Task 5: Pantry router + templates

This task establishes the full pattern used by all subsequent tabs.

**Files:**
- Modify: `app/routers/pantry.py`
- Create: `app/templates/pantry.html`
- Create: `app/templates/partials/pantry_rows.html`
- Create: `app/templates/partials/pantry_dialog.html`
- Create: `tests/test_pantry.py`

**Step 1: Write failing tests**

`tests/test_pantry.py`:
```python
from meal_planner.core import pantry as pantry_core
from meal_planner.db.models import PantryItem


def test_pantry_page_returns_200(authed_client):
    resp = authed_client.get("/pantry")
    assert resp.status_code == 200
    assert "pantry" in resp.text.lower()


def test_pantry_add_form_returns_dialog(authed_client):
    resp = authed_client.get("/pantry/add")
    assert resp.status_code == 200
    assert "<dialog" in resp.text


def test_pantry_add_saves_and_returns_rows(authed_client):
    resp = authed_client.post("/pantry/add", data={
        "name": "Test Apple", "brand": "", "category": "Fruit",
        "location": "Fridge", "quantity": "3", "unit": "each",
        "best_by": "", "preferred_store_id": "", "barcode": "",
        "product_notes": "", "item_notes": "", "estimated_price": "",
    })
    assert resp.status_code == 200
    assert "Test Apple" in resp.text


def test_pantry_delete_returns_empty(authed_client):
    # Add an item first
    authed_client.post("/pantry/add", data={"name": "ToDelete", "quantity": "1"})
    items = pantry_core.get_all()
    item = next(i for i in items if i.name == "ToDelete")
    resp = authed_client.delete(f"/pantry/{item.id}")
    assert resp.status_code == 200
    assert resp.text.strip() == ""


def test_pantry_filter_rows(authed_client):
    resp = authed_client.get("/pantry/rows?location=Fridge")
    assert resp.status_code == 200
```

**Step 2: Run tests — expect failures**

```bash
pytest tests/test_pantry.py -v
```

Expected: All fail.

**Step 3: Implement `app/routers/pantry.py`**

```python
import os
import shutil
import tempfile
from datetime import date

from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core import pantry as pantry_core
from meal_planner.db.models import PantryItem

router = APIRouter(prefix="/pantry", tags=["pantry"])
templates = Jinja2Templates(directory="app/templates")
TODAY = str(date.today())


def _ctx(request, **kwargs):
    """Base template context for pantry pages."""
    return {"request": request, "active_tab": "pantry", "demo": False, **kwargs}


def _store_map(stores):
    return {s.id: s.name for s in stores}


@router.get("", response_class=HTMLResponse)
def pantry_page(request: Request, location: str = "", category: str = ""):
    items = pantry_core.get_all(location=location or None, category=category or None)
    stores = pantry_core.get_all_stores()
    return templates.TemplateResponse("pantry.html", _ctx(
        request,
        items=items,
        stores=stores,
        store_map=_store_map(stores),
        locations=[""] + pantry_core.get_locations(),
        categories=[""] + pantry_core.get_categories(),
        filter_location=location,
        filter_category=category,
        today=TODAY,
    ))


@router.get("/rows", response_class=HTMLResponse)
def pantry_rows(request: Request, location: str = "", category: str = ""):
    items = pantry_core.get_all(location=location or None, category=category or None)
    stores = pantry_core.get_all_stores()
    return templates.TemplateResponse("partials/pantry_rows.html", {
        "request": request, "items": items,
        "store_map": _store_map(stores), "today": TODAY,
    })


@router.get("/add", response_class=HTMLResponse)
def pantry_add_form(request: Request):
    return templates.TemplateResponse("partials/pantry_dialog.html", _ctx(
        request,
        item=None,
        stores=pantry_core.get_all_stores(),
        locations=pantry_core.get_locations(),
        categories=pantry_core.get_categories(),
    ))


@router.post("/add", response_class=HTMLResponse)
def pantry_add(
    request: Request,
    name: str = Form(...),
    brand: str = Form(""),
    category: str = Form(""),
    location: str = Form(""),
    quantity: float = Form(1.0),
    unit: str = Form(""),
    best_by: str = Form(""),
    preferred_store_id: str = Form(""),
    barcode: str = Form(""),
    product_notes: str = Form(""),
    item_notes: str = Form(""),
    estimated_price: str = Form(""),
):
    item = PantryItem(
        id=None, name=name,
        barcode=barcode or None, category=category or None,
        location=location or None, brand=brand or None,
        quantity=quantity, unit=unit or None, best_by=best_by or None,
        preferred_store_id=int(preferred_store_id) if preferred_store_id else None,
        product_notes=product_notes or None, item_notes=item_notes or None,
        estimated_price=float(estimated_price) if estimated_price else None,
    )
    pantry_core.add(item)
    items = pantry_core.get_all()
    stores = pantry_core.get_all_stores()
    return templates.TemplateResponse("partials/pantry_rows.html", {
        "request": request, "items": items,
        "store_map": _store_map(stores), "today": TODAY,
    })


@router.get("/{item_id}/edit", response_class=HTMLResponse)
def pantry_edit_form(request: Request, item_id: int):
    return templates.TemplateResponse("partials/pantry_dialog.html", _ctx(
        request,
        item=pantry_core.get(item_id),
        stores=pantry_core.get_all_stores(),
        locations=pantry_core.get_locations(),
        categories=pantry_core.get_categories(),
    ))


@router.post("/{item_id}/edit", response_class=HTMLResponse)
def pantry_edit(
    request: Request, item_id: int,
    name: str = Form(...),
    brand: str = Form(""),
    category: str = Form(""),
    location: str = Form(""),
    quantity: float = Form(1.0),
    unit: str = Form(""),
    best_by: str = Form(""),
    preferred_store_id: str = Form(""),
    barcode: str = Form(""),
    product_notes: str = Form(""),
    item_notes: str = Form(""),
    estimated_price: str = Form(""),
):
    item = pantry_core.get(item_id)
    item.name = name
    item.brand = brand or None
    item.category = category or None
    item.location = location or None
    item.quantity = quantity
    item.unit = unit or None
    item.best_by = best_by or None
    item.preferred_store_id = int(preferred_store_id) if preferred_store_id else None
    item.barcode = barcode or None
    item.product_notes = product_notes or None
    item.item_notes = item_notes or None
    item.estimated_price = float(estimated_price) if estimated_price else None
    pantry_core.update(item)
    items = pantry_core.get_all()
    stores = pantry_core.get_all_stores()
    return templates.TemplateResponse("partials/pantry_rows.html", {
        "request": request, "items": items,
        "store_map": _store_map(stores), "today": TODAY,
    })


@router.delete("/{item_id}", response_class=HTMLResponse)
def pantry_delete(item_id: int):
    pantry_core.delete(item_id)
    return HTMLResponse("")  # HTMX removes the row via hx-swap="outerHTML"


@router.post("/import", response_class=HTMLResponse)
def pantry_import(request: Request, file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        inserted, updated = pantry_core.import_csv(tmp_path)
        message = f"Imported: {inserted} new items, {updated} updated."
        flash_type = "success"
    except Exception as e:
        message = f"Import failed: {e}"
        flash_type = "error"
    finally:
        os.unlink(tmp_path)
    items = pantry_core.get_all()
    stores = pantry_core.get_all_stores()
    return templates.TemplateResponse("partials/pantry_rows.html", {
        "request": request, "items": items,
        "store_map": _store_map(stores), "today": TODAY,
        "flash_message": message, "flash_type": flash_type,
    })
```

**Step 4: Create `app/templates/pantry.html`**

```html
{% extends "base.html" %}
{% block title %}Pantry — Meal Planner{% endblock %}
{% block content %}

<div class="toolbar">
  <select hx-get="/pantry/rows" hx-target="#pantry-tbody"
          hx-include="[name='category']" name="location">
    {% for loc in locations %}
      <option value="{{ loc }}" {{ 'selected' if loc == filter_location }}>
        {{ loc or 'All Locations' }}
      </option>
    {% endfor %}
  </select>

  <select hx-get="/pantry/rows" hx-target="#pantry-tbody"
          hx-include="[name='location']" name="category">
    {% for cat in categories %}
      <option value="{{ cat }}" {{ 'selected' if cat == filter_category }}>
        {{ cat or 'All Categories' }}
      </option>
    {% endfor %}
  </select>

  {% if not demo %}
  <button class="btn btn-primary"
          hx-get="/pantry/add" hx-target="#modal-container">+ Add Item</button>

  <label class="btn btn-secondary" style="cursor:pointer">
    Import CSV
    <input type="file" name="file" accept=".csv" style="display:none"
           hx-post="/pantry/import" hx-target="#pantry-tbody"
           hx-encoding="multipart/form-data" hx-trigger="change">
  </label>
  {% endif %}

  <span class="htmx-indicator"><span class="spinner"></span></span>
</div>

<table>
  <thead>
    <tr>
      <th>Name</th><th>Brand</th><th>Category</th><th>Location</th>
      <th>Qty</th><th>Unit</th><th>Best By</th><th>Store</th>
      {% if not demo %}<th></th>{% endif %}
    </tr>
  </thead>
  <tbody id="pantry-tbody">
    {% include "partials/pantry_rows.html" %}
  </tbody>
</table>
{% endblock %}
```

**Step 5: Create `app/templates/partials/pantry_rows.html`**

```html
{% for item in items %}
{% set is_expired  = item.best_by and item.best_by < today %}
{% set is_expiring = item.best_by and item.best_by >= today and item.best_by <= today[:8] ~ (today[8:]|int + 7)|string %}
<tr id="pantry-row-{{ item.id }}"
    class="{{ 'expired' if is_expired else ('expiring' if is_expiring else '') }}">
  <td>{{ item.name }}</td>
  <td>{{ item.brand or '' }}</td>
  <td>{{ item.category or '' }}</td>
  <td>{{ item.location or '' }}</td>
  <td>{{ item.quantity }}</td>
  <td>{{ item.unit or '' }}</td>
  <td>{{ item.best_by or '' }}</td>
  <td>{{ store_map.get(item.preferred_store_id, '') }}</td>
  {% if not demo %}
  <td style="white-space:nowrap">
    <button class="btn btn-secondary btn-sm"
            hx-get="/pantry/{{ item.id }}/edit"
            hx-target="#modal-container">Edit</button>
    <button class="btn btn-danger btn-sm"
            hx-delete="/pantry/{{ item.id }}"
            hx-target="#pantry-row-{{ item.id }}"
            hx-swap="outerHTML"
            hx-confirm="Delete {{ item.name }}?">Del</button>
  </td>
  {% endif %}
</tr>
{% else %}
<tr><td colspan="9" style="text-align:center;color:#94a3b8;padding:2rem">
  No items found.
</td></tr>
{% endfor %}
```

Note on the expiring-soon row class: the Jinja2 date comparison above uses string comparison (ISO dates sort correctly). For a cleaner approach, pass `expiring_ids` as a set from the router using `pantry_core.get_expiring_soon(7)`.

**Improved approach** — add to the router's `_ctx` or pass directly:
```python
expiring_ids = {i.id for i in pantry_core.get_expiring_soon(7)}
```
Then in the template: `class="{{ 'expired' if is_expired else ('expiring' if item.id in expiring_ids else '') }}"`.

Update the routes that render `pantry_rows.html` to pass `expiring_ids`.

**Step 6: Create `app/templates/partials/pantry_dialog.html`**

```html
<dialog>
  <form method="post"
        action="{{ '/pantry/' ~ item.id ~ '/edit' if item else '/pantry/add' }}"
        hx-post="{{ '/pantry/' ~ item.id ~ '/edit' if item else '/pantry/add' }}"
        hx-target="#pantry-tbody"
        hx-swap="innerHTML"
        hx-on::after-request="this.closest('dialog').remove()">

    <div class="dialog-header">
      <h2>{{ 'Edit Item' if item else 'Add Pantry Item' }}</h2>
      <button type="button" onclick="this.closest('dialog').remove()">&times;</button>
    </div>

    <div class="dialog-body">
      <div class="form-row">
        <div class="form-group">
          <label>Name *</label>
          <input type="text" name="name" value="{{ item.name if item else '' }}" required>
        </div>
        <div class="form-group">
          <label>Brand</label>
          <input type="text" name="brand" value="{{ item.brand or '' }}">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Category</label>
          <input type="text" name="category" value="{{ item.category or '' }}"
                 list="category-list">
          <datalist id="category-list">
            {% for c in categories %}<option value="{{ c }}">{% endfor %}
          </datalist>
        </div>
        <div class="form-group">
          <label>Location</label>
          <select name="location">
            <option value="">—</option>
            {% for loc in ['Pantry', 'Fridge', 'Freezer'] %}
            <option value="{{ loc }}" {{ 'selected' if item and item.location == loc }}>
              {{ loc }}
            </option>
            {% endfor %}
          </select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Quantity</label>
          <input type="number" name="quantity" step="0.01"
                 value="{{ item.quantity if item else '1' }}">
        </div>
        <div class="form-group">
          <label>Unit</label>
          <input type="text" name="unit" value="{{ item.unit or '' }}">
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Best By</label>
          <input type="date" name="best_by" value="{{ item.best_by or '' }}">
        </div>
        <div class="form-group">
          <label>Preferred Store</label>
          <select name="preferred_store_id">
            <option value="">—</option>
            {% for s in stores %}
            <option value="{{ s.id }}"
              {{ 'selected' if item and item.preferred_store_id == s.id }}>
              {{ s.name }}
            </option>
            {% endfor %}
          </select>
        </div>
      </div>
      <div class="form-group">
        <label>Barcode</label>
        <input type="text" name="barcode" value="{{ item.barcode or '' }}">
      </div>
      <div class="form-group">
        <label>Estimated Price ($)</label>
        <input type="number" name="estimated_price" step="0.01"
               value="{{ item.estimated_price or '' }}">
      </div>
    </div>

    <div class="dialog-footer">
      <button type="button" class="btn btn-secondary"
              onclick="this.closest('dialog').remove()">Cancel</button>
      <button type="submit" class="btn btn-primary">
        {{ 'Save Changes' if item else 'Add Item' }}
      </button>
    </div>
  </form>
</dialog>
```

**Step 7: Run tests — expect pass**

```bash
pytest tests/test_pantry.py -v
```

Expected: All pass.

**Step 8: Manual smoke test**

Navigate to `/pantry`. Verify: table loads, filters work, add/edit dialog opens, delete removes rows, CSV import works.

**Step 9: Commit**

```bash
git add app/routers/pantry.py app/templates/
git commit -m "feat: pantry tab — full CRUD with HTMX table + modal dialogs"
```

---

## Task 6: Stores router + templates

**Files:**
- Modify: `app/routers/stores.py`
- Create: `app/templates/stores.html`
- Create: `app/templates/partials/stores_rows.html`
- Create: `app/templates/partials/stores_dialog.html`

Stores is the simplest tab (no filters, 3 fields). Follow the exact same pattern as Task 5.

**Route signatures:**

```python
router = APIRouter(prefix="/stores", tags=["stores"])

GET  /stores              → stores.html  (full page, table of all stores)
GET  /stores/add          → partials/stores_dialog.html (item=None)
POST /stores/add          → save Store → return partials/stores_rows.html
GET  /stores/{id}/edit    → partials/stores_dialog.html (item=store)
POST /stores/{id}/edit    → update → return partials/stores_rows.html
DELETE /stores/{id}       → stores_core.delete(id) → HTMLResponse("")
```

**Core functions to call:**
```python
from meal_planner.core import stores as stores_core
stores_core.get_all()          # → [Store]
stores_core.get(id)            # → Store
stores_core.add(store)         # → int
stores_core.update(store)      # → None
stores_core.delete(id)         # → None
```

**Store form fields:** `name` (required), `location`, `notes`.

**stores_rows.html** — table with Name, Location, Notes, Edit/Delete buttons (same pattern as pantry_rows).

**stores_dialog.html** — dialog with 3 form fields (name, location, notes).

Write a minimal test:
```python
def test_stores_page(authed_client):
    resp = authed_client.get("/stores")
    assert resp.status_code == 200

def test_stores_add(authed_client):
    resp = authed_client.post("/stores/add",
        data={"name": "Whole Foods", "location": "Downtown", "notes": ""})
    assert resp.status_code == 200
    assert "Whole Foods" in resp.text
```

**Commit:**
```bash
git add app/routers/stores.py app/templates/stores.html app/templates/partials/stores_*
git commit -m "feat: stores tab — CRUD"
```

---

## Task 7: Recipes router + templates

**Files:**
- Modify: `app/routers/recipes.py`
- Create: `app/templates/recipes.html`
- Create: `app/templates/partials/recipe_list.html`
- Create: `app/templates/partials/recipe_detail.html`
- Create: `app/templates/partials/recipe_dialog.html` (add/edit form)
- Create: `app/templates/partials/recipe_ai_form.html` (paste text / URL input)
- Create: `tests/test_recipes.py`

**Route signatures:**

```python
router = APIRouter(prefix="/recipes", tags=["recipes"])

GET  /recipes                   → recipes.html (split-pane layout, list left, empty detail right)
GET  /recipes/list?q=           → partials/recipe_list.html (HTMX: search filter)
GET  /recipes/{id}              → partials/recipe_detail.html (HTMX: click to load detail)
GET  /recipes/add               → partials/recipe_dialog.html (item=None)
POST /recipes/add               → save → redirect /recipes/{id}
GET  /recipes/{id}/edit         → partials/recipe_dialog.html (item=recipe)
POST /recipes/{id}/edit         → update → partials/recipe_detail.html
DELETE /recipes/{id}            → delete → HTMLResponse("") + HX-Redirect header

# AI operations — all sync def (FastAPI runs in thread pool)
GET  /recipes/ai/paste          → partials/recipe_ai_form.html (mode="paste")
POST /recipes/ai/parse-text     → parse text → partials/recipe_dialog.html pre-filled
GET  /recipes/ai/url            → partials/recipe_ai_form.html (mode="url")
POST /recipes/ai/parse-url      → parse url  → partials/recipe_dialog.html pre-filled
POST /recipes/ai/generate       → generate   → partials/recipe_dialog.html pre-filled
GET  /recipes/{id}/ai/modify    → partials/recipe_ai_form.html (mode="modify", recipe_id=id)
POST /recipes/{id}/ai/modify    → modify     → partials/recipe_dialog.html pre-filled
```

**Core functions:**
```python
from meal_planner.core import recipes as recipes_core
from meal_planner.core.ai_assistant import (
    parse_recipe_text, parse_recipe_url, generate_recipe, modify_recipe
)

recipes_core.get_all()          # → [Recipe]
recipes_core.get(id)            # → Recipe (with ingredients)
recipes_core.search(query)      # → [Recipe]
recipes_core.add(recipe)        # → int
recipes_core.update(recipe)     # → None
recipes_core.delete(id)         # → None
```

**Key implementation notes:**

1. AI routes take several seconds — use `hx-indicator` on the submit button:
   ```html
   <button type="submit" hx-disabled-elt="this">
     <span class="htmx-indicator spinner"></span> Generating...
   </button>
   ```

2. AI result goes into `recipe_dialog.html` as a pre-filled form (not saved yet). User reviews and clicks "Save Recipe".

3. For delete with redirect: return `HTMLResponse("", headers={"HX-Redirect": "/recipes"})`.

4. Recipe edit dialog has a dynamic ingredient list. Use HTMX to add/remove ingredient rows:
   - "Add ingredient" button appends a row via `hx-get="/recipes/ingredient-row" hx-target="#ingredients-list" hx-swap="beforeend"`
   - Each row has a "Remove" button that does `hx-delete` on that row element

5. `recipe_dialog.html` ingredient form: name each ingredient field with an index, e.g., `ingredient_name_0`, `ingredient_qty_0`, etc. The router collects them by iterating the form data.

**Collecting variable ingredient fields in FastAPI:**
```python
@router.post("/add")
async def recipe_add(request: Request):
    form = await request.form()
    name = form["name"]
    # Collect ingredients by scanning form keys
    ingredients = []
    i = 0
    while f"ingredient_name_{i}" in form:
        ing_name = form[f"ingredient_name_{i}"].strip()
        if ing_name:
            ingredients.append(RecipeIngredient(
                id=None, recipe_id=None,
                name=ing_name,
                quantity=float(form.get(f"ingredient_qty_{i}") or 0) or None,
                unit=form.get(f"ingredient_unit_{i}") or None,
            ))
        i += 1
    recipe = Recipe(id=None, name=name, ..., ingredients=ingredients)
    recipe_id = recipes_core.add(recipe)
    return RedirectResponse(url=f"/recipes/{recipe_id}", status_code=303)
```

**Test stubs:**
```python
def test_recipes_page(authed_client):
    resp = authed_client.get("/recipes")
    assert resp.status_code == 200

def test_recipe_add_and_detail(authed_client):
    resp = authed_client.post("/recipes/add", data={
        "name": "Test Soup", "description": "", "servings": "4",
        "prep_time": "", "cook_time": "", "instructions": "",
        "source_url": "", "tags": "", "rating": "",
        "ingredient_name_0": "Carrot", "ingredient_qty_0": "2", "ingredient_unit_0": "cups",
    }, follow_redirects=True)
    assert resp.status_code == 200

def test_recipe_ai_paste_form(authed_client):
    resp = authed_client.get("/recipes/ai/paste")
    assert resp.status_code == 200
    assert "textarea" in resp.text.lower()
```

**Commit:**
```bash
git add app/routers/recipes.py app/templates/recipes.html app/templates/partials/recipe_*
git commit -m "feat: recipes tab — CRUD + AI operations (parse, generate, modify)"
```

---

## Task 8: Meal Plan router + templates

**Files:**
- Modify: `app/routers/meal_plan.py`
- Create: `app/templates/meal_plan.html`
- Create: `app/templates/partials/meal_grid.html`
- Create: `app/templates/partials/meal_picker.html`
- Create: `app/templates/partials/meal_ai_suggest.html`
- Create: `tests/test_meal_plan.py`

**Route signatures:**

```python
router = APIRouter(prefix="/meal-plan", tags=["meal_plan"])

GET  /meal-plan                     → meal_plan.html (current week)
GET  /meal-plan?week=2026-02-23     → meal_plan.html (specific week by Monday date)
GET  /meal-plan/grid?week=          → partials/meal_grid.html (HTMX week navigation)
GET  /meal-plan/pick/{date}/{slot}  → partials/meal_picker.html (recipe picker dialog)
POST /meal-plan/set                 → set_meal() → partials/meal_grid.html
POST /meal-plan/clear               → clear_meal() → partials/meal_grid.html
POST /meal-plan/ai/suggest          → suggest_week() → partials/meal_ai_suggest.html
POST /meal-plan/ai/apply            → apply suggestions → partials/meal_grid.html
```

**Core functions:**
```python
from meal_planner.core import meal_plan as mp_core, recipes as recipes_core
from meal_planner.core.ai_assistant import suggest_week

mp_core.get_week_start(for_date)    # → date (Monday)
mp_core.get_week(start_date)        # → {date_str: {slot: MealPlanEntry}}
mp_core.set_meal(date, slot, recipe_id, servings, notes)
mp_core.clear_meal(date, slot)
```

**Key notes:**

1. Week navigation: "Prev" / "Next" / "Today" buttons use HTMX:
   ```html
   <button hx-get="/meal-plan/grid?week={{ prev_week }}" hx-target="#meal-grid">← Prev</button>
   ```

2. `meal_grid.html` renders a 4×7 grid (slots × days). Each cell is clickable:
   ```html
   <div class="meal-cell {{ 'filled' if entry else '' }}"
        hx-get="/meal-plan/pick/{{ date }}/{{ slot }}"
        hx-target="#modal-container">
     {% if entry and entry.recipe_name %}
       <div class="meal-cell-name">{{ entry.recipe_name }}</div>
       <div class="meal-cell-servings">× {{ entry.servings }}</div>
     {% else %}
       <span style="color:#cbd5e1;font-size:11px">+</span>
     {% endif %}
   </div>
   ```

3. `meal_picker.html` shows a searchable list of recipes (all recipes from DB) + a "Clear" button + servings input. Submits to `POST /meal-plan/set`.

4. AI suggest: posts to `/meal-plan/ai/suggest`, returns suggestions in `meal_ai_suggest.html` showing proposed day/slot/recipe. "Apply" button posts to `/meal-plan/ai/apply` with the accepted suggestions.

5. The `suggest_week` AI call returns `[{"day": "Monday", "slot": "Dinner", "recipe": "Pasta"}]`. Match by recipe name (case-insensitive) against the recipes DB.

**Test stubs:**
```python
def test_meal_plan_page(authed_client):
    resp = authed_client.get("/meal-plan")
    assert resp.status_code == 200

def test_meal_plan_grid_partial(authed_client):
    resp = authed_client.get("/meal-plan/grid?week=2026-02-23")
    assert resp.status_code == 200
```

**Commit:**
```bash
git add app/routers/meal_plan.py app/templates/meal_plan.html app/templates/partials/meal_*
git commit -m "feat: meal plan tab — weekly grid, meal picker, AI suggest week"
```

---

## Task 9: Shopping router + templates

**Files:**
- Modify: `app/routers/shopping.py`
- Create: `app/templates/shopping.html`
- Create: `app/templates/partials/shopping_list.html`
- Create: `tests/test_shopping.py`

**Route signatures:**

```python
router = APIRouter(prefix="/shopping", tags=["shopping"])

GET  /shopping                  → shopping.html (date pickers + pantry toggle)
POST /shopping/generate         → call generate() → partials/shopping_list.html
POST /shopping/export           → call format_shopping_list() → plain text response
```

**Core functions:**
```python
from meal_planner.core.shopping_list import generate, format_shopping_list

shopping = generate(start_date, end_date, use_pantry=True)
# Returns: {store_name: [(name, qty, unit, cost), ...]}

text = format_shopping_list(shopping)
```

**Key notes:**

1. `shopping.html` has two `<input type="date">` for start/end, a "This Week" button (JS sets both inputs to Mon–Sun of current week), and a "Subtract pantry items" checkbox.

2. The generate form uses HTMX:
   ```html
   <form hx-post="/shopping/generate" hx-target="#shopping-results">
     <input type="date" name="start_date">
     <input type="date" name="end_date">
     <input type="checkbox" name="use_pantry" checked>
     <button type="submit">Generate</button>
   </form>
   ```

3. `shopping_list.html` renders the grouped result as checkboxes:
   ```html
   {% for store, items in shopping.items() %}
   <div class="shopping-store">
     <h3>{{ store }}</h3>
     {% for name, qty, unit, cost in items %}
     <div class="shopping-item">
       <input type="checkbox" id="item-{{ loop.index }}">
       <label for="item-{{ loop.index }}">
         {{ name }} — {{ qty|round(2) }} {{ unit }}
       </label>
       {% if cost %}<span class="cost">${{ "%.2f"|format(cost) }}</span>{% endif %}
     </div>
     {% endfor %}
   </div>
   {% endfor %}
   ```

4. Export: POST `/shopping/export` returns the plain-text list as a downloadable response:
   ```python
   from fastapi.responses import PlainTextResponse
   return PlainTextResponse(text, headers={
       "Content-Disposition": "attachment; filename=shopping_list.txt"
   })
   ```

5. "Copy to clipboard" can be a small JS snippet (no HTMX needed):
   ```html
   <button onclick="navigator.clipboard.writeText(document.getElementById('list-text').textContent)">
     Copy to Clipboard
   </button>
   ```

**Test stubs:**
```python
def test_shopping_page(authed_client):
    resp = authed_client.get("/shopping")
    assert resp.status_code == 200

def test_shopping_generate_empty(authed_client):
    resp = authed_client.post("/shopping/generate", data={
        "start_date": "2026-02-23", "end_date": "2026-03-01", "use_pantry": "on"
    })
    assert resp.status_code == 200
```

**Commit:**
```bash
git add app/routers/shopping.py app/templates/shopping.html app/templates/partials/shopping_*
git commit -m "feat: shopping list tab — generate, display, export"
```

---

## Task 10: Settings route (Claude API key)

**Files:**
- Modify: `app/routers/settings.py`
- Create: `app/templates/settings.html`

**Route signatures:**

```python
router = APIRouter(prefix="/settings", tags=["settings"])

GET  /settings      → settings.html (Claude API key field, masked)
POST /settings      → save key → redirect /settings with flash
```

**Core functions:**
```python
from meal_planner.config import get_setting, set_setting

get_setting("claude_api_key")          # → str or None
set_setting("claude_api_key", value)   # → None
```

**settings.html** — simple form with one password-type input for the API key. Show first 8 chars + `****` if already set, empty otherwise.

```python
@router.get("", response_class=HTMLResponse)
def settings_page(request: Request):
    key = get_setting("claude_api_key") or ""
    masked = key[:8] + "..." if len(key) > 8 else ""
    return templates.TemplateResponse("settings.html", {
        "request": request, "active_tab": "settings",
        "demo": False, "key_set": bool(key), "masked_key": masked,
    })

@router.post("")
def settings_save(request: Request, claude_api_key: str = Form("")):
    if claude_api_key.strip():
        set_setting("claude_api_key", claude_api_key.strip())
    return RedirectResponse(url="/settings?saved=1", status_code=303)
```

**Commit:**
```bash
git add app/routers/settings.py app/templates/settings.html
git commit -m "feat: settings page — Claude API key management"
```

---

## Task 11: Demo mode

**Files:**
- Create: `demo/__init__.py`
- Create: `demo/seed.py`
- Modify: `app/routers/pantry.py` (add `/demo/pantry` routes)
- Modify: `app/routers/recipes.py` (add `/demo/recipes` routes)
- Modify: `app/routers/meal_plan.py` (add `/demo/meal-plan` routes)
- Modify: `app/routers/shopping.py` (add `/demo/shopping` route)
- Modify: `app/routers/stores.py` (add `/demo/stores` route)
- Modify: `app/main.py` (register demo router)
- Create: `app/routers/demo.py` (demo router that wraps all tabs)
- Create: `tests/test_demo.py`

**Step 1: Create `demo/seed.py`**

```python
"""Seed the demo database with fake data if it's empty."""
import os
from pathlib import Path
from meal_planner.db.database import _db_path_override, init_db
from meal_planner.core import pantry as pantry_core, recipes as recipes_core
from meal_planner.core import meal_plan as mp_core, stores as stores_core
from meal_planner.db.models import Store, PantryItem, Recipe, RecipeIngredient, MealPlanEntry


DEMO_RECIPES = [
    Recipe(id=None, name="Spaghetti Bolognese", description="Classic Italian pasta",
           servings=4, prep_time="15 min", cook_time="45 min",
           tags="pasta,italian,dinner",
           instructions="1. Brown beef.\n2. Add tomato sauce.\n3. Simmer 30 min.\n4. Serve over pasta.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="ground beef", quantity=1, unit="lb"),
               RecipeIngredient(id=None, recipe_id=None, name="spaghetti", quantity=12, unit="oz"),
               RecipeIngredient(id=None, recipe_id=None, name="tomato sauce", quantity=24, unit="oz"),
               RecipeIngredient(id=None, recipe_id=None, name="onion", quantity=1, unit="medium"),
               RecipeIngredient(id=None, recipe_id=None, name="garlic", quantity=3, unit="cloves"),
           ]),
    Recipe(id=None, name="Chicken Stir Fry", description="Quick weeknight dinner",
           servings=2, prep_time="10 min", cook_time="15 min",
           tags="chicken,quick,asian,dinner",
           instructions="1. Slice chicken.\n2. Stir fry with vegetables.\n3. Add sauce.\n4. Serve with rice.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="chicken breast", quantity=1, unit="lb"),
               RecipeIngredient(id=None, recipe_id=None, name="broccoli", quantity=2, unit="cups"),
               RecipeIngredient(id=None, recipe_id=None, name="soy sauce", quantity=3, unit="tbsp"),
               RecipeIngredient(id=None, recipe_id=None, name="rice", quantity=1, unit="cup"),
           ]),
    Recipe(id=None, name="Avocado Toast", description="Quick healthy breakfast",
           servings=1, prep_time="5 min", cook_time="3 min",
           tags="breakfast,quick,vegetarian",
           instructions="1. Toast bread.\n2. Mash avocado.\n3. Top with seasoning.",
           ingredients=[
               RecipeIngredient(id=None, recipe_id=None, name="bread", quantity=2, unit="slices"),
               RecipeIngredient(id=None, recipe_id=None, name="avocado", quantity=1, unit="whole"),
           ]),
    # Add 5-6 more recipes following same pattern...
]

DEMO_PANTRY = [
    PantryItem(id=None, name="Chicken Breast", category="Meat", location="Freezer",
               quantity=3, unit="lbs", best_by="2026-04-01"),
    PantryItem(id=None, name="Pasta", category="Dry Goods", location="Pantry",
               quantity=2, unit="lbs"),
    PantryItem(id=None, name="Canned Tomatoes", category="Canned Goods", location="Pantry",
               quantity=4, unit="cans"),
    PantryItem(id=None, name="Greek Yogurt", category="Dairy", location="Fridge",
               quantity=1, unit="container", best_by="2026-03-05"),
    PantryItem(id=None, name="Eggs", category="Dairy", location="Fridge",
               quantity=12, unit="count", best_by="2026-03-10"),
    # Add more...
]


def seed_if_empty():
    """Seed demo DB if it has no recipes yet."""
    existing = recipes_core.get_all()
    if existing:
        return  # Already seeded

    # Add a store
    store_id = stores_core.add(Store(id=None, name="Demo Grocery", location="123 Main St"))

    # Add recipes
    recipe_ids = []
    for recipe in DEMO_RECIPES:
        recipe_ids.append(recipes_core.add(recipe))

    # Add pantry items
    for item in DEMO_PANTRY:
        item.preferred_store_id = store_id
        pantry_core.add(item)

    # Add meal plan entries for current week
    from datetime import date, timedelta
    from meal_planner.core.meal_plan import get_week_start
    week_start = get_week_start()
    slots = ["Breakfast", "Lunch", "Dinner"]
    for day_offset in range(7):
        day = week_start + timedelta(days=day_offset)
        for slot_idx, slot in enumerate(slots):
            rid = recipe_ids[(day_offset * 3 + slot_idx) % len(recipe_ids)]
            mp_core.set_meal(str(day), slot, rid, servings=1)
```

**Step 2: Create `app/routers/demo.py`**

```python
"""Demo router — read-only views of all tabs backed by the demo DB.

Sets _db_path_override ContextVar so all core/ functions use demo.db.
Blocks all write operations (POST/DELETE) with HTTP 403.
"""
import os
from contextlib import contextmanager
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from meal_planner.db.database import _db_path_override
from meal_planner.core import pantry as pantry_core, recipes as recipes_core
from meal_planner.core import meal_plan as mp_core, stores as stores_core
from meal_planner.core.shopping_list import generate as shopping_generate

router = APIRouter(prefix="/demo", tags=["demo"])
templates = Jinja2Templates(directory="app/templates")

DEMO_DB_PATH = Path(os.environ.get("DEMO_DB_URL", "data/demo.db"))


@contextmanager
def _demo_db():
    token = _db_path_override.set(DEMO_DB_PATH)
    try:
        yield
    finally:
        _db_path_override.reset(token)


def _ctx(request, active_tab, **kwargs):
    return {"request": request, "active_tab": active_tab, "demo": True, **kwargs}


@router.get("/pantry", response_class=HTMLResponse)
def demo_pantry(request: Request):
    with _demo_db():
        items = pantry_core.get_all()
        stores = pantry_core.get_all_stores()
        store_map = {s.id: s.name for s in stores}
    return templates.TemplateResponse("pantry.html", _ctx(
        request, "pantry",
        items=items, stores=stores, store_map=store_map,
        locations=[""], categories=[""],
        filter_location="", filter_category="", today="",
        expiring_ids=set(),
    ))


@router.get("/recipes", response_class=HTMLResponse)
def demo_recipes(request: Request):
    with _demo_db():
        all_recipes = recipes_core.get_all()
    return templates.TemplateResponse("recipes.html", _ctx(
        request, "recipes", recipes=all_recipes, selected=None
    ))


@router.get("/recipes/{recipe_id}", response_class=HTMLResponse)
def demo_recipe_detail(request: Request, recipe_id: int):
    with _demo_db():
        recipe = recipes_core.get(recipe_id)
    return templates.TemplateResponse("partials/recipe_detail.html", _ctx(
        request, "recipes", recipe=recipe
    ))


@router.get("/meal-plan", response_class=HTMLResponse)
def demo_meal_plan(request: Request, week: str = ""):
    from datetime import date
    from meal_planner.core.meal_plan import get_week_start, MEAL_SLOTS
    week_start = get_week_start(date.fromisoformat(week) if week else None)
    with _demo_db():
        week_data = mp_core.get_week(week_start)
    return templates.TemplateResponse("meal_plan.html", _ctx(
        request, "meal_plan", week_data=week_data,
        week_start=week_start, slots=MEAL_SLOTS,
    ))


@router.get("/shopping", response_class=HTMLResponse)
def demo_shopping(request: Request):
    return templates.TemplateResponse("shopping.html", _ctx(request, "shopping"))


@router.post("/shopping/generate", response_class=HTMLResponse)
def demo_shopping_generate(request: Request,
                            start_date: str = "",
                            end_date: str = ""):
    with _demo_db():
        shopping = shopping_generate(start_date, end_date, use_pantry=False)
    return templates.TemplateResponse("partials/shopping_list.html", _ctx(
        request, "shopping", shopping=shopping
    ))


@router.get("/stores", response_class=HTMLResponse)
def demo_stores(request: Request):
    with _demo_db():
        stores = stores_core.get_all()
    return templates.TemplateResponse("stores.html", _ctx(
        request, "stores", stores=stores
    ))
```

**Step 3: Register demo router in `app/main.py`**

```python
from app.routers import demo
# ... after other includes:
app.include_router(demo.router)
```

The `is_public()` function in `dependencies.py` already allows `/demo` paths.

**Step 4: Update templates to pass `demo=True` flag**

The base template already handles `demo=True` (banner, disabled buttons). The pantry, stores, recipes, meal_plan, shopping templates already have `{% if not demo %}` guards around write buttons (written in Tasks 5–9). Verify each template passes `demo` through correctly.

**Step 5: Write tests**

`tests/test_demo.py`:
```python
def test_demo_pantry_accessible_without_auth(client):
    # Use a fresh client with no session
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as fresh:
        resp = fresh.get("/demo/pantry")
    assert resp.status_code == 200


def test_demo_recipes_accessible_without_auth(client):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as fresh:
        resp = fresh.get("/demo/recipes")
    assert resp.status_code == 200


def test_demo_shows_banner(client):
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as fresh:
        resp = fresh.get("/demo/pantry")
    assert "demo mode" in resp.text.lower()
```

**Step 6: Run all tests**

```bash
pytest tests/ -v
```

Expected: All pass.

**Step 7: Commit**

```bash
git add demo/ app/routers/demo.py
git commit -m "feat: demo mode — read-only /demo/* routes with seeded fake data"
```

---

## Task 12: Docker setup

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

**Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory (will be overridden by volume mount)
RUN mkdir -p /data

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Step 2: Create `docker-compose.yml`**

```yaml
services:
  app:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
    environment:
      - APP_PASSWORD=${APP_PASSWORD:-changeme}
      - SECRET_KEY=${SECRET_KEY:-change-this-in-production}
      - DATABASE_URL=/data/meal_planner.db
      - DEMO_DB_URL=/data/demo.db
      - CLAUDE_API_KEY=${CLAUDE_API_KEY:-}
    restart: unless-stopped
```

**Step 3: Create `.dockerignore`**

```
.git
.env
__pycache__
*.pyc
*.pyo
.pytest_cache
tests/
meal_planner/gui/
*.md
docs/
```

**Step 4: Create `data/` directory with a `.gitkeep`**

```bash
mkdir -p data
touch data/.gitkeep
echo "data/*.db" >> .gitignore
```

**Step 5: Build and run**

```bash
APP_PASSWORD=mypassword SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") docker compose up --build
```

Visit `http://localhost:8080` — login, verify all tabs work.

**Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore data/.gitkeep .gitignore
git commit -m "feat: Docker setup — Dockerfile, docker-compose, data volume"
```

---

## Task 13: Cleanup

**Files:**
- Delete: `meal_planner/gui/` (entire directory)
- Delete: `main.py` (the PySide6 entry point — or repurpose it)
- Modify: `CLAUDE.md` (update to reflect web architecture)

**Step 1: Verify all tests pass before deleting anything**

```bash
pytest tests/ -v
```

Expected: All pass.

**Step 2: Delete the GUI layer**

```bash
rm -rf meal_planner/gui/
```

**Step 3: Check if `main.py` (PySide6 entry point) can be deleted**

Read the current `main.py`. If it only imports from `gui/` and launches Qt, delete it:
```bash
rm main.py
```

The new entry point is `uvicorn app.main:app`.

**Step 4: Run tests again to confirm nothing broke**

```bash
pytest tests/ -v
```

Expected: All still pass (no imports of `gui/` in test suite).

**Step 5: Update `CLAUDE.md`**

Replace the GUI section with the new web architecture. Update:
- Running section: `uvicorn app.main:app --reload --port 8080`
- Architecture diagram: replace gui/ with app/ (routers, templates)
- Module dependency map: update to reflect web structure
- Remove PySide6-specific patterns

**Step 6: Final commit**

```bash
git add -A
git commit -m "chore: remove PySide6 GUI, update CLAUDE.md for web architecture"
```

---

## Running the App

**Local development:**
```bash
cp .env.example .env   # fill in APP_PASSWORD, CLAUDE_API_KEY
uvicorn app.main:app --reload --port 8080
```

**Docker (local):**
```bash
docker compose up --build
```

**Docker (remote/production):**
```bash
# On your server — same command, with env vars from .env or secrets manager
docker compose up -d
```

**Demo mode** is always available at `/demo/*` — no login required.
