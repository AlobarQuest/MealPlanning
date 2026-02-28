# Web Migration Design — Meal Planner

**Date:** 2026-02-27
**Status:** Approved
**Approach:** A — Minimal-friction port (FastAPI + HTMX)

---

## Overview

Migrate the Meal Planner PySide6 desktop app to a FastAPI + HTMX web app. The existing `db/` and `core/` layers are preserved unchanged. Only the `gui/` layer is replaced. The app runs in Docker, is accessible remotely, and includes a read-only demo mode with seeded fake data.

---

## Goals

- Single-user web app accessible locally and remotely
- Docker-based deployment (Coolify or similar)
- Single password auth (env var) with signed session cookie
- Read-only demo mode at `/demo/*` with fake seeded data
- Local dev without Docker: `uvicorn app.main:app --reload`

---

## Project Structure

```
MealPlanning/
├── meal_planner/
│   ├── db/          ← unchanged (connection management, schema, models)
│   ├── core/        ← unchanged (business logic — called directly from routers)
│   └── gui/         ← deleted
├── app/
│   ├── main.py          ← FastAPI app, lifespan, middleware, router registration
│   ├── dependencies.py  ← get_db_path(), require_auth(), demo_guard(), CSRF
│   ├── routers/
│   │   ├── auth.py          ← GET/POST /login, POST /logout
│   │   ├── pantry.py        ← /pantry (list, add, edit, delete, CSV import)
│   │   ├── recipes.py       ← /recipes (list, detail, add, edit, delete, AI ops)
│   │   ├── meal_plan.py     ← /meal-plan (week view, set/clear meal, AI suggest)
│   │   ├── shopping.py      ← /shopping (generate, export/copy)
│   │   └── stores.py        ← /stores (list, add, edit, delete)
│   ├── templates/
│   │   ├── base.html        ← nav tabs, flash messages, demo banner, CSRF
│   │   ├── login.html
│   │   ├── partials/        ← HTMX partial responses (table rows, dialogs, etc.)
│   │   └── [tab].html       ← one full-page template per tab
│   └── static/
│       ├── htmx.min.js
│       └── style.css
├── demo/
│   └── seed.py      ← creates demo.db with fake recipes, pantry, meal plan
├── data/            ← Docker volume mount point
│   ├── meal_planner.db
│   └── demo.db
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Auth & Session Design

- **Password:** Single `APP_PASSWORD` env var
- **Session:** Signed cookie via `itsdangerous` (same as BookingAssistant)
- **Secret key:** `SECRET_KEY` env var

### Routes

```
GET  /login     → login form
POST /login     → verify password → set session → redirect /pantry
POST /logout    → clear session → redirect /login
```

All routes except `/login` and `/demo/*` require auth via `require_auth` FastAPI dependency. Unauthenticated requests redirect to `/login`.

---

## Routing & HTMX Pattern

Each tab maps to a router. Full page loads return complete HTML; HTMX interactions return partials only. Pattern (pantry as example):

```
GET    /pantry                          → full page (table + filters)
GET    /pantry/rows?location=&cat=      → HTMX partial: <tbody> rows (filtering)
GET    /pantry/add                      → HTMX partial: add dialog/form
POST   /pantry/add                      → save → return updated <tbody>
GET    /pantry/{id}/edit                → HTMX partial: edit dialog/form
POST   /pantry/{id}/edit                → save → return updated row
DELETE /pantry/{id}                     → delete → HTMX removes row
POST   /pantry/import                   → CSV upload → result message + table
```

All five tabs follow the same pattern. AI operations (parse recipe, generate, suggest week) POST and return a confirmation/edit form as a partial before the user commits the save.

No JavaScript framework — HTMX handles async via `hx-post`, `hx-get`, `hx-target`, `hx-swap`.

---

## Demo Mode

- **Route prefix:** `/demo/*` — no auth required
- **Database:** Separate `data/demo.db`, seeded by `demo/seed.py`
- **Seed data:** ~15 fake recipes, stocked pantry items, one week of meal plan entries
- **Writes:** Blocked by `demo_guard` dependency → HTTP 403 on any POST/DELETE
- **UI:** Demo banner in `base.html` when `demo=True`; write buttons hidden/disabled
- **Seeding:** Run at container startup via lifespan if `demo.db` doesn't exist

Demo routes use the same routers/templates as the main app, with `demo=True` passed as a template context flag and a separate DB path injected via dependency.

---

## Docker Setup

### docker-compose.yml

```yaml
services:
  app:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
    environment:
      - APP_PASSWORD=changeme
      - SECRET_KEY=changeme
      - DATABASE_URL=/data/meal_planner.db
      - DEMO_DB_URL=/data/demo.db
      - CLAUDE_API_KEY=sk-ant-...
```

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Data persistence

SQLite files live in `./data/` on the host, mounted into `/data/` in the container. Both `meal_planner.db` and `demo.db` persist across restarts and image rebuilds.

---

## Dependencies to Add

```
fastapi>=0.115.0
uvicorn>=0.30.0
jinja2>=3.1.0
python-multipart>=0.0.9   # form parsing
itsdangerous>=2.2.0       # session signing
python-dotenv>=1.0.0      # .env loading for local dev
```

Existing: `anthropic`, `httpx` (kept as-is).
Removed: `PySide6` (no longer needed).

---

## Migration Sequence

1. Scaffold `app/` directory: `main.py`, `dependencies.py`, `routers/`, `templates/`, `static/`
2. Implement auth (login/logout/session)
3. Port each tab as a router + templates (Pantry → Stores → Recipes → Meal Plan → Shopping)
4. Implement demo mode (`demo/seed.py`, demo guard, demo banner)
5. Docker: `Dockerfile`, `docker-compose.yml`, `.env.example`
6. Delete `meal_planner/gui/`
7. Validate all features against the original desktop app behavior

---

## What Does NOT Change

- `meal_planner/db/` — connection management, schema, `init_db()`
- `meal_planner/core/` — all business logic (pantry, recipes, meal_plan, shopping_list, ai_assistant, staples, stores, known_prices)
- `meal_planner/db/models.py` — dataclass models
- `config.py` — settings management (Claude API key stored in DB settings table)
- SQLite as the database (no migration to Postgres needed for single-user)
- The AI integration in `core/ai_assistant.py` — same Claude API calls
