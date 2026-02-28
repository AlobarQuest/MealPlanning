from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core import stores as stores_core
from meal_planner.db.models import Store

router = APIRouter(prefix="/stores", tags=["stores"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
def stores_page(request: Request):
    return templates.TemplateResponse(request, "stores.html", {
        "active_tab": "stores", "demo": False,
        "stores": stores_core.get_all(),
    })


@router.get("/add", response_class=HTMLResponse)
def stores_add_form(request: Request):
    return templates.TemplateResponse(request, "partials/stores_dialog.html", {
        "store": None,
    })


@router.post("/add", response_class=HTMLResponse)
def stores_add(
    request: Request,
    name: str = Form(...),
    location: str = Form(""),
    notes: str = Form(""),
):
    stores_core.add(Store(id=None, name=name, location=location or None, notes=notes or None))
    return templates.TemplateResponse(request, "partials/stores_rows.html", {
        "stores": stores_core.get_all(), "demo": False,
    })


@router.get("/{store_id}/edit", response_class=HTMLResponse)
def stores_edit_form(request: Request, store_id: int):
    store = stores_core.get(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return templates.TemplateResponse(request, "partials/stores_dialog.html", {
        "store": store,
    })


@router.post("/{store_id}/edit", response_class=HTMLResponse)
def stores_edit(
    request: Request,
    store_id: int,
    name: str = Form(...),
    location: str = Form(""),
    notes: str = Form(""),
):
    store = stores_core.get(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    store.name = name
    store.location = location or None
    store.notes = notes or None
    stores_core.update(store)
    return templates.TemplateResponse(request, "partials/stores_rows.html", {
        "stores": stores_core.get_all(), "demo": False,
    })


@router.delete("/{store_id}", response_class=HTMLResponse)
def stores_delete(store_id: int):
    stores_core.delete(store_id)
    return HTMLResponse("")
