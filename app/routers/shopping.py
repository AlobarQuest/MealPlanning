from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core.shopping_list import generate, format_shopping_list
from meal_planner.core import meal_plan as mp_core

router = APIRouter(prefix="/shopping", tags=["shopping"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _week_defaults() -> tuple[str, str]:
    today = date.today()
    week_start = mp_core.get_week_start(today)
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


@router.get("", response_class=HTMLResponse)
def shopping_page(request: Request):
    start_default, end_default = _week_defaults()
    return templates.TemplateResponse(request, "shopping.html", {
        "active_tab": "shopping",
        "demo": False,
        "start_default": start_default,
        "end_default": end_default,
    })


@router.post("/generate", response_class=HTMLResponse)
async def shopping_generate(request: Request):
    form = await request.form()
    start_date = form.get("start_date", "")
    end_date = form.get("end_date", "")
    use_pantry = form.get("use_pantry") is not None

    if not start_date or not end_date:
        start_date, end_date = _week_defaults()

    shopping = generate(start_date, end_date, use_pantry=use_pantry)
    plain_text = format_shopping_list(shopping)

    return templates.TemplateResponse(request, "partials/shopping_list.html", {
        "shopping": shopping,
        "plain_text": plain_text,
        "start_date": start_date,
        "end_date": end_date,
    })


@router.post("/export")
async def shopping_export(request: Request):
    form = await request.form()
    start_date = form.get("start_date", "")
    end_date = form.get("end_date", "")
    use_pantry = form.get("use_pantry") is not None

    if not start_date or not end_date:
        start_date, end_date = _week_defaults()

    shopping = generate(start_date, end_date, use_pantry=use_pantry)
    text = format_shopping_list(shopping)
    return PlainTextResponse(text, headers={
        "Content-Disposition": "attachment; filename=shopping_list.txt",
    })
