def test_stores_page_returns_200(authed_client):
    resp = authed_client.get("/stores")
    assert resp.status_code == 200
    assert "store" in resp.text.lower()


def test_stores_add_form_returns_dialog(authed_client):
    resp = authed_client.get("/stores/add")
    assert resp.status_code == 200
    assert "<dialog" in resp.text


def test_stores_add_saves_store(authed_client):
    resp = authed_client.post("/stores/add", data={
        "name": "Test Market", "location": "Downtown", "notes": ""
    })
    assert resp.status_code == 200
    assert "Test Market" in resp.text


def test_stores_delete_returns_empty(authed_client):
    from meal_planner.core import stores as stores_core
    authed_client.post("/stores/add", data={"name": "DeleteMe", "location": "", "notes": ""})
    stores = stores_core.get_all()
    store = next(s for s in stores if s.name == "DeleteMe")
    resp = authed_client.delete(f"/stores/{store.id}")
    assert resp.status_code == 200
    assert resp.text.strip() == ""
