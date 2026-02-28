from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core import meal_plan as mp_core, recipes as recipes_core
from meal_planner.core.ai_assistant import suggest_week

router = APIRouter(prefix="/meal-plan", tags=["meal_plan"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")

SLOTS = mp_core.MEAL_SLOTS
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _parse_week(week_str: str = None) -> date:
    if week_str:
        try:
            return date.fromisoformat(week_str)
        except (ValueError, TypeError):
            pass
    return mp_core.get_week_start()


def _week_context(week_start: date) -> dict:
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    return {
        "week_start": week_start,
        "week_str": week_start.isoformat(),
        "week_dates": week_dates,
        "day_names": DAY_NAMES,
        "slots": SLOTS,
        "week_grid": mp_core.get_week(week_start),
        "prev_week": (week_start - timedelta(days=7)).isoformat(),
        "next_week": (week_start + timedelta(days=7)).isoformat(),
        "today_week": mp_core.get_week_start().isoformat(),
    }


# ── Page & grid ────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
def meal_plan_page(request: Request, week: str = None):
    week_start = _parse_week(week)
    return templates.TemplateResponse(request, "meal_plan.html", {
        "active_tab": "meal_plan", "demo": False,
        **_week_context(week_start),
    })


@router.get("/grid", response_class=HTMLResponse)
def meal_plan_grid(request: Request, week: str = None):
    week_start = _parse_week(week)
    return templates.TemplateResponse(request, "partials/meal_grid.html", {
        "demo": False, **_week_context(week_start),
    })


# ── Meal picker ────────────────────────────────────────────────────────────────

@router.get("/pick/{entry_date}/{slot}", response_class=HTMLResponse)
def meal_picker(request: Request, entry_date: str, slot: str):
    try:
        d = date.fromisoformat(entry_date)
    except (ValueError, TypeError):
        d = date.today()
    week_start = mp_core.get_week_start(d)
    grid = mp_core.get_week(week_start)
    current = grid.get(entry_date, {}).get(slot)
    return templates.TemplateResponse(request, "partials/meal_picker.html", {
        "recipes": recipes_core.get_all(),
        "entry_date": entry_date,
        "slot": slot,
        "current": current,
        "week_str": week_start.isoformat(),
    })


# ── Set / clear ────────────────────────────────────────────────────────────────

@router.post("/set", response_class=HTMLResponse)
async def meal_set(request: Request):
    form = await request.form()
    entry_date = form["date"]
    slot = form["slot"]
    recipe_id_str = (form.get("recipe_id") or "").strip()
    servings_str = (form.get("servings") or "1").strip()
    notes = (form.get("notes") or "").strip()
    recipe_id = int(recipe_id_str) if recipe_id_str else None
    servings = int(servings_str) if servings_str else 1
    mp_core.set_meal(entry_date, slot, recipe_id, servings, notes or None)
    week_start = _parse_week(form.get("week"))
    return templates.TemplateResponse(request, "partials/meal_grid.html", {
        "demo": False, **_week_context(week_start),
    })


@router.post("/clear", response_class=HTMLResponse)
async def meal_clear(request: Request):
    form = await request.form()
    mp_core.clear_meal(form["date"], form["slot"])
    week_start = _parse_week(form.get("week"))
    return templates.TemplateResponse(request, "partials/meal_grid.html", {
        "demo": False, **_week_context(week_start),
    })


# ── AI suggest ─────────────────────────────────────────────────────────────────

@router.post("/ai/suggest", response_class=HTMLResponse)
def meal_ai_suggest(
    request: Request,
    preferences: str = Form(""),
    week: str = Form(""),
):
    week_start = _parse_week(week or None)
    all_recipes = recipes_core.get_all()
    suggestions = suggest_week(all_recipes, preferences)
    return templates.TemplateResponse(request, "partials/meal_ai_suggest.html", {
        "suggestions": suggestions,
        "week_str": week_start.isoformat(),
    })


@router.post("/ai/apply", response_class=HTMLResponse)
async def meal_ai_apply(request: Request):
    form = await request.form()
    week_start = _parse_week(form.get("week"))
    day_to_date = {
        day_name: (week_start + timedelta(days=idx)).isoformat()
        for idx, day_name in enumerate(DAY_NAMES)
    }
    all_recipes = {r.name.lower(): r for r in recipes_core.get_all()}

    i = 0
    while f"sug_day_{i}" in form:
        day = form[f"sug_day_{i}"]
        slot = form[f"sug_slot_{i}"]
        meal_name = (form.get(f"sug_meal_{i}") or "").strip()
        if day in day_to_date and slot in SLOTS and meal_name:
            entry_date = day_to_date[day]
            recipe = all_recipes.get(meal_name.lower())
            recipe_id = recipe.id if recipe else None
            notes = None if recipe_id else meal_name
            mp_core.set_meal(entry_date, slot, recipe_id, 1, notes)
        i += 1

    return templates.TemplateResponse(request, "partials/meal_grid.html", {
        "demo": False, **_week_context(week_start),
    })
