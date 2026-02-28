import os
import shutil
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from meal_planner.core import pantry as pantry_core
from meal_planner.db.models import PantryItem

router = APIRouter(prefix="/pantry", tags=["pantry"])
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


def _ctx(request: Request, **kwargs) -> dict:
    return {"active_tab": "pantry", "demo": False, **kwargs}


def _store_map(stores) -> dict:
    return {s.id: s.name for s in stores}


def _today() -> str:
    return str(date.today())


@router.get("", response_class=HTMLResponse)
def pantry_page(request: Request, location: str = "", category: str = ""):
    items = pantry_core.get_all(location=location or None, category=category or None)
    stores = pantry_core.get_all_stores()
    expiring_ids = {i.id for i in pantry_core.get_expiring_soon(7)}
    return templates.TemplateResponse(request, "pantry.html", _ctx(
        request,
        items=items,
        stores=stores,
        store_map=_store_map(stores),
        locations=[""] + pantry_core.get_locations(),
        categories=[""] + pantry_core.get_categories(),
        filter_location=location,
        filter_category=category,
        today=_today(),
        expiring_ids=expiring_ids,
    ))


@router.get("/rows", response_class=HTMLResponse)
def pantry_rows(request: Request, location: str = "", category: str = ""):
    items = pantry_core.get_all(location=location or None, category=category or None)
    stores = pantry_core.get_all_stores()
    expiring_ids = {i.id for i in pantry_core.get_expiring_soon(7)}
    return templates.TemplateResponse(request, "partials/pantry_rows.html", {
        "items": items,
        "store_map": _store_map(stores),
        "today": _today(),
        "expiring_ids": expiring_ids,
        "demo": False,
    })


@router.get("/add", response_class=HTMLResponse)
def pantry_add_form(request: Request):
    return templates.TemplateResponse(request, "partials/pantry_dialog.html", {
        "item": None,
        "stores": pantry_core.get_all_stores(),
        "locations": pantry_core.get_locations(),
        "categories": pantry_core.get_categories(),
    })


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
        id=None,
        name=name,
        barcode=barcode or None,
        category=category or None,
        location=location or None,
        brand=brand or None,
        quantity=quantity,
        unit=unit or None,
        best_by=best_by or None,
        preferred_store_id=int(preferred_store_id) if preferred_store_id else None,
        product_notes=product_notes or None,
        item_notes=item_notes or None,
        estimated_price=float(estimated_price) if estimated_price else None,
    )
    pantry_core.add(item)
    items = pantry_core.get_all()
    stores = pantry_core.get_all_stores()
    expiring_ids = {i.id for i in pantry_core.get_expiring_soon(7)}
    return templates.TemplateResponse(request, "partials/pantry_rows.html", {
        "items": items,
        "store_map": _store_map(stores),
        "today": _today(),
        "expiring_ids": expiring_ids,
        "demo": False,
    })


@router.get("/{item_id}/edit", response_class=HTMLResponse)
def pantry_edit_form(request: Request, item_id: int):
    return templates.TemplateResponse(request, "partials/pantry_dialog.html", {
        "item": pantry_core.get(item_id),
        "stores": pantry_core.get_all_stores(),
        "locations": pantry_core.get_locations(),
        "categories": pantry_core.get_categories(),
    })


@router.post("/{item_id}/edit", response_class=HTMLResponse)
def pantry_edit(
    request: Request,
    item_id: int,
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
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
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
    expiring_ids = {i.id for i in pantry_core.get_expiring_soon(7)}
    return templates.TemplateResponse(request, "partials/pantry_rows.html", {
        "items": items,
        "store_map": _store_map(stores),
        "today": _today(),
        "expiring_ids": expiring_ids,
        "demo": False,
    })


@router.delete("/{item_id}", response_class=HTMLResponse)
def pantry_delete(item_id: int):
    pantry_core.delete(item_id)
    return HTMLResponse("")


@router.post("/import", response_class=HTMLResponse)
def pantry_import(request: Request, file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        inserted, updated = pantry_core.import_csv(tmp_path)
        flash_message = f"Imported: {inserted} new items, {updated} updated."
        flash_type = "success"
    except Exception as e:
        flash_message = f"Import failed: {e}"
        flash_type = "error"
    finally:
        os.unlink(tmp_path)
    items = pantry_core.get_all()
    stores = pantry_core.get_all_stores()
    expiring_ids = {i.id for i in pantry_core.get_expiring_soon(7)}
    return templates.TemplateResponse(request, "partials/pantry_rows.html", {
        "items": items,
        "store_map": _store_map(stores),
        "today": _today(),
        "expiring_ids": expiring_ids,
        "demo": False,
        "flash_message": flash_message,
        "flash_type": flash_type,
    })
