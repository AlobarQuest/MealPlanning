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
