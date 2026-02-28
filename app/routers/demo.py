"""Demo router — read-only views of all tabs backed by the demo DB.

Sets db path override ContextVar so all core/ functions use demo.db.
Write operations (POST/DELETE) are blocked for most routes; only
/demo/shopping/generate is allowed (it's read-only computation).
"""
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.db.database import override_db_path
from meal_planner.core import pantry as pantry_core, recipes as recipes_core
from meal_planner.core import meal_plan as mp_core, stores as stores_core
from meal_planner.core.shopping_list import generate as shopping_generate, format_shopping_list

router = APIRouter(prefix="/demo", tags=["demo"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _demo_db_path() -> Path:
    return Path(os.environ.get("DEMO_DB_URL", "data/demo.db"))


def _ctx(request: Request, active_tab: str, **kwargs) -> dict:
    return {"request": request, "active_tab": active_tab, "demo": True, **kwargs}


# ── Pantry ─────────────────────────────────────────────────────────────────────

@router.get("/pantry", response_class=HTMLResponse)
def demo_pantry(request: Request):
    with override_db_path(_demo_db_path()):
        items = pantry_core.get_all()
        stores = pantry_core.get_all_stores()
        store_map = {s.id: s.name for s in stores}
        expiring_ids = {i.id for i in pantry_core.get_expiring_soon(7)}
        locations = [""] + pantry_core.get_locations()
        categories = [""] + pantry_core.get_categories()
    return templates.TemplateResponse(request, "pantry.html", _ctx(
        request, "pantry",
        items=items, stores=stores, store_map=store_map,
        expiring_ids=expiring_ids,
        locations=locations, categories=categories,
        filter_location="", filter_category="", today="",
    ))


# ── Recipes ────────────────────────────────────────────────────────────────────

@router.get("/recipes", response_class=HTMLResponse)
def demo_recipes(request: Request):
    with override_db_path(_demo_db_path()):
        recipe_list = recipes_core.get_all()
    return templates.TemplateResponse(request, "recipes.html", _ctx(
        request, "recipes", recipes=recipe_list,
    ))


@router.get("/recipes/{recipe_id}", response_class=HTMLResponse)
def demo_recipe_detail(request: Request, recipe_id: int):
    with override_db_path(_demo_db_path()):
        recipe = recipes_core.get(recipe_id)
    return templates.TemplateResponse(request, "partials/recipe_detail.html", {
        "recipe": recipe, "demo": True,
    })


# ── Meal plan ──────────────────────────────────────────────────────────────────

@router.get("/meal-plan", response_class=HTMLResponse)
def demo_meal_plan(request: Request, week: str = ""):
    from datetime import date as date_type
    from meal_planner.core.meal_plan import get_week_start, MEAL_SLOTS
    from datetime import timedelta

    try:
        week_start = get_week_start(date_type.fromisoformat(week)) if week else get_week_start()
    except (ValueError, TypeError):
        week_start = get_week_start()

    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    with override_db_path(_demo_db_path()):
        week_grid = mp_core.get_week(week_start)

    return templates.TemplateResponse(request, "meal_plan.html", _ctx(
        request, "meal_plan",
        week_start=week_start,
        week_str=week_start.isoformat(),
        week_dates=week_dates,
        day_names=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        slots=MEAL_SLOTS,
        week_grid=week_grid,
        prev_week=(week_start + timedelta(days=-7)).isoformat(),
        next_week=(week_start + timedelta(days=7)).isoformat(),
        today_week=get_week_start().isoformat(),
    ))


@router.get("/meal-plan/grid", response_class=HTMLResponse)
def demo_meal_plan_grid(request: Request, week: str = ""):
    from datetime import date as date_type
    from meal_planner.core.meal_plan import get_week_start, MEAL_SLOTS
    from datetime import timedelta

    try:
        week_start = get_week_start(date_type.fromisoformat(week)) if week else get_week_start()
    except (ValueError, TypeError):
        week_start = get_week_start()

    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    with override_db_path(_demo_db_path()):
        week_grid = mp_core.get_week(week_start)

    return templates.TemplateResponse(request, "partials/meal_grid.html", {
        "demo": True,
        "week_start": week_start,
        "week_str": week_start.isoformat(),
        "week_dates": week_dates,
        "day_names": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "slots": MEAL_SLOTS,
        "week_grid": week_grid,
        "prev_week": (week_start + timedelta(days=-7)).isoformat(),
        "next_week": (week_start + timedelta(days=7)).isoformat(),
        "today_week": get_week_start().isoformat(),
    })


# ── Shopping ───────────────────────────────────────────────────────────────────

@router.get("/shopping", response_class=HTMLResponse)
def demo_shopping(request: Request):
    from datetime import date as date_type, timedelta
    from meal_planner.core import meal_plan as mp_core2
    today = date_type.today()
    week_start = mp_core2.get_week_start(today)
    return templates.TemplateResponse(request, "shopping.html", _ctx(
        request, "shopping",
        start_default=week_start.isoformat(),
        end_default=(week_start + timedelta(days=6)).isoformat(),
    ))


@router.post("/shopping/generate", response_class=HTMLResponse)
async def demo_shopping_generate(request: Request):
    form = await request.form()
    start_date = form.get("start_date", "")
    end_date = form.get("end_date", "")
    with override_db_path(_demo_db_path()):
        shopping = shopping_generate(start_date, end_date, use_pantry=False)
        plain_text = format_shopping_list(shopping)
    return templates.TemplateResponse(request, "partials/shopping_list.html", {
        "shopping": shopping,
        "plain_text": plain_text,
        "start_date": start_date,
        "end_date": end_date,
        "demo": True,
    })


# ── Stores ─────────────────────────────────────────────────────────────────────

@router.get("/stores", response_class=HTMLResponse)
def demo_stores(request: Request):
    with override_db_path(_demo_db_path()):
        store_list = stores_core.get_all()
    return templates.TemplateResponse(request, "stores.html", _ctx(
        request, "stores", stores=store_list,
    ))
