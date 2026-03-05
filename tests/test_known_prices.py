from meal_planner.core import known_prices as prices_core
from meal_planner.core import stores as stores_core
from meal_planner.db.models import Store


def test_prices_list_renders_in_stores_page(authed_client):
    resp = authed_client.get("/stores")
    assert resp.status_code == 200
    assert "price book" in resp.text.lower() or "prices" in resp.text.lower()


def test_prices_list_partial_returns_200(authed_client):
    resp = authed_client.get("/stores/prices")
    assert resp.status_code == 200


def test_prices_add_form_returns_dialog(authed_client):
    resp = authed_client.get("/stores/prices/add")
    assert resp.status_code == 200
    assert "<dialog" in resp.text


def test_prices_add_saves_price(authed_client):
    resp = authed_client.post("/stores/prices/add", data={
        "item_name": "Olive Oil", "unit_price": "8.99", "unit": "bottle", "store_id": ""
    })
    assert resp.status_code == 200
    assert "Olive Oil" in resp.text


def test_prices_delete_removes_price(authed_client):
    prices_core.upsert("DeleteMe", 1.99)
    price = next(p for p in prices_core.get_all() if p.item_name == "DeleteMe")
    resp = authed_client.delete(f"/stores/prices/{price.id}")
    assert resp.status_code == 200
    assert resp.text.strip() == ""
    assert prices_core.get_by_name("DeleteMe") is None


def test_prices_filter_by_store(authed_client):
    store_id = stores_core.add(Store(id=None, name="FilterStore"))
    prices_core.upsert("Butter", 3.49, store_id=store_id)
    resp = authed_client.get(f"/stores/prices?store_id={store_id}")
    assert resp.status_code == 200
    assert "Butter" in resp.text


def test_prices_import_form_returns_dialog(authed_client):
    resp = authed_client.get("/stores/prices/import")
    assert resp.status_code == 200
    assert "<dialog" in resp.text
    assert "receipt" in resp.text.lower()


def test_prices_import_save_bulk_upserts(authed_client):
    resp = authed_client.post("/stores/prices/import/save", data={
        "store_id": "",
        "item_name": ["Eggs", "Milk"],
        "unit_price": ["3.99", "4.49"],
        "unit": ["dozen", "gallon"],
        "include": ["0", "1"],
    })
    assert resp.status_code == 200
    eggs = prices_core.get_by_name("Eggs")
    assert eggs is not None
    assert eggs.unit_price == 3.99


def test_prices_import_save_skips_unchecked(authed_client):
    resp = authed_client.post("/stores/prices/import/save", data={
        "store_id": "",
        "item_name": ["Butter", "Cheese"],
        "unit_price": ["5.99", "7.99"],
        "unit": ["", ""],
        "include": ["0"],  # only first item checked
    })
    assert resp.status_code == 200
    assert prices_core.get_by_name("Butter") is not None
    assert prices_core.get_by_name("Cheese") is None


def test_demo_stores_shows_price_book():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.get("/demo/stores")
    assert resp.status_code == 200
    assert "price book" in resp.text.lower() or "prices" in resp.text.lower()
