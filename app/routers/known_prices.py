"""Known prices router — Price Book section within the Stores tab."""
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core import known_prices as prices_core
from meal_planner.core import stores as stores_core
from meal_planner.core.ai_assistant import parse_receipt

router = APIRouter(prefix="/stores/prices", tags=["known_prices"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _price_list_ctx(store_id: int = 0):
    all_prices = prices_core.get_all()
    if store_id:
        all_prices = [p for p in all_prices if p.store_id == store_id]
    all_stores = stores_core.get_all()
    store_map = {s.id: s.name for s in all_stores}
    return {"prices": all_prices, "store_map": store_map,
            "stores": all_stores, "filter_store_id": store_id}


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
    })


@router.delete("/{price_id}", response_class=HTMLResponse)
def prices_delete(price_id: int):
    prices_core.delete(price_id)
    return HTMLResponse("")
