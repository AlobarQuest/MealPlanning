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
