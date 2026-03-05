from meal_planner.core import staples as staples_core
from meal_planner.db.models import Staple


def test_staples_list_returns_200(authed_client):
    resp = authed_client.get("/pantry/staples")
    assert resp.status_code == 200
    assert "staple" in resp.text.lower() or "on hand" in resp.text.lower()


def test_staples_add_form_returns_dialog(authed_client):
    resp = authed_client.get("/pantry/staples/add")
    assert resp.status_code == 200
    assert "<dialog" in resp.text


def test_staples_add_saves_staple(authed_client):
    resp = authed_client.post("/pantry/staples/add", data={"name": "Olive Oil"})
    assert resp.status_code == 200
    assert "Olive Oil" in resp.text


def test_staples_edit_form_returns_dialog(authed_client):
    staples_core.add(Staple(id=None, name="Salt"))
    staple = next(s for s in staples_core.get_all() if s.name == "Salt")
    resp = authed_client.get(f"/pantry/staples/{staple.id}/edit")
    assert resp.status_code == 200
    assert "Salt" in resp.text


def test_staples_edit_saves_changes(authed_client):
    staples_core.add(Staple(id=None, name="Pepper"))
    staple = next(s for s in staples_core.get_all() if s.name == "Pepper")
    resp = authed_client.post(f"/pantry/staples/{staple.id}/edit", data={"name": "Black Pepper"})
    assert resp.status_code == 200
    assert "Black Pepper" in resp.text


def test_staples_delete_removes_staple(authed_client):
    staples_core.add(Staple(id=None, name="DeleteMe"))
    staple = next(s for s in staples_core.get_all() if s.name == "DeleteMe")
    resp = authed_client.delete(f"/pantry/staples/{staple.id}")
    assert resp.status_code == 200
    assert resp.text.strip() == ""
    assert staples_core.get(staple.id) is None


def test_staples_bulk_status_mark_needed(authed_client):
    id1 = staples_core.add(Staple(id=None, name="Flour"))
    id2 = staples_core.add(Staple(id=None, name="Sugar"))
    resp = authed_client.post("/pantry/staples/bulk-status", data={
        "staple_ids": [str(id1), str(id2)], "need": "1"
    })
    assert resp.status_code == 200
    assert staples_core.get(id1).need_to_buy is True
    assert staples_core.get(id2).need_to_buy is True
    assert "Needed" in resp.text


def test_staples_bulk_status_mark_onhand(authed_client):
    staple_id = staples_core.add(Staple(id=None, name="Vinegar", need_to_buy=True))
    resp = authed_client.post("/pantry/staples/bulk-status", data={
        "staple_ids": [str(staple_id)], "need": "0"
    })
    assert resp.status_code == 200
    assert staples_core.get(staple_id).need_to_buy is False


def test_demo_staples_accessible_without_auth():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.get("/demo/pantry/staples", follow_redirects=False)
    assert resp.status_code == 200


def test_demo_staples_hides_write_buttons():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        resp = c.get("/demo/pantry/staples")
    assert "Add Staple" not in resp.text
    assert "Mark as Needed" not in resp.text
