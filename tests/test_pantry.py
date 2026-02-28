def test_pantry_page_returns_200(authed_client):
    resp = authed_client.get("/pantry")
    assert resp.status_code == 200
    assert "pantry" in resp.text.lower()


def test_pantry_rows_partial(authed_client):
    resp = authed_client.get("/pantry/rows")
    assert resp.status_code == 200


def test_pantry_add_form_returns_dialog(authed_client):
    resp = authed_client.get("/pantry/add")
    assert resp.status_code == 200
    assert "<dialog" in resp.text


def test_pantry_add_saves_item(authed_client):
    resp = authed_client.post("/pantry/add", data={
        "name": "Test Apple", "brand": "", "category": "Fruit",
        "location": "Fridge", "quantity": "3", "unit": "each",
        "best_by": "", "preferred_store_id": "", "barcode": "",
        "product_notes": "", "item_notes": "", "estimated_price": "",
    })
    assert resp.status_code == 200
    assert "Test Apple" in resp.text


def test_pantry_delete_returns_empty(authed_client):
    from meal_planner.core import pantry as pantry_core
    authed_client.post("/pantry/add", data={"name": "ToDelete", "quantity": "1"})
    items = pantry_core.get_all()
    item = next(i for i in items if i.name == "ToDelete")
    resp = authed_client.delete(f"/pantry/{item.id}")
    assert resp.status_code == 200
    assert resp.text.strip() == ""


def test_pantry_filter_rows(authed_client):
    resp = authed_client.get("/pantry/rows?location=Fridge")
    assert resp.status_code == 200
